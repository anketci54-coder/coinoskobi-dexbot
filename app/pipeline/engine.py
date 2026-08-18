import json
import logging
import threading

from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair import analyze as pair_analyze
from app.risk.bytecode import analyze as risk_analyze
from app.risk.gate import RiskGate
from app.risk.sellability import analyze as sellability_analyze
from app.risk.traps import TrapRiskAnalyzer
from app.risk.mev import MEVExposureAnalyzer
from app.risk.paper_position_sizing import (
    PAPER_CAPITAL_USDT,
    calculate_paper_position_size,
)
from app.risk.dynamic_stop_loss import calculate_dynamic_sl

from app.strategy.engine import StrategyEngine
from app.strategy.unified_score import UnifiedScoreEngine
from app.strategy.decision import UnifiedDecisionEngine
from app.strategy.execution_cost import ExecutionCostEngine

from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice
from app.paper.manager import PaperManager

from app.cache.gecko_cache import GeckoCache
from app.filter.cache_filter import CacheFilter
from app.filter.ingress_gate import IngressGate
from app.pipeline.simulation_drift_composition import (
    build_phase15_drift_composition,
)
from app.pipeline.candidate_queue import CandidateAdmissionQueue
from app.pipeline.conveyor import ConveyorLabeler
from app.pipeline.work_scheduler import WorkScheduler
from app.pipeline.market_context import build_market_context
from app.pipeline.execution_context import build_execution_context
from app.pipeline.paper_admission import paper_admission_decision
from app.pipeline.intelligence_composition import RuntimeIntelligenceComposition
from app.pipeline.command_center import build_command_center_readmodel
from app.pipeline.operating_mode import build_operating_mode_readmodel
from app.pipeline.operator_command import build_operator_command
from app.pipeline.tactical_truth import build_tactical_truth
from app.learning.runtime_outcome_feed import RuntimeLearningOutcomeFeed
from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)
from app.learning.entry_context import (
    build_entry_signal_attribution,
    build_exit_baseline,
)
from app.dex.pair_membership import verify_pair_membership
from app.dex.runtime_market_flow import RuntimeMarketFlowStore
from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.scanner.adapters.source_router import normalize_source_rows
from app.scanner.gecko_scanner import GeckoScanner

from app.config.scanner import (
    ANALYZER_WORKERS,
    MAX_PENDING_CANDIDATES,
    RECENT_ANALYSIS_COOLDOWN_SECONDS,
)

from app.config.trading import (
    DEFAULT_AMOUNT_BNB,
    MAX_OPEN_PAPER_POSITIONS,
    TP_PRICE_MULTIPLIER,
    SL_PRICE_MULTIPLIER,
    DEFAULT_GAS_BUY,
    DEFAULT_GAS_SELL,
    DEFAULT_SWAP_FEE,
    DEFAULT_BUY_TAX,
    DEFAULT_SELL_TAX,
    DEFAULT_SLIPPAGE,
    DEFAULT_MEV_COST,
)

logger = logging.getLogger(__name__)

_strategy = StrategyEngine()
_unified_score = UnifiedScoreEngine()
_unified_decision = UnifiedDecisionEngine()
_execution_cost = ExecutionCostEngine()
_risk_gate = RiskGate()
_trap_risk = TrapRiskAnalyzer()
_mev_risk = MEVExposureAnalyzer()

from app.learning.unified_outcome_readmodel import (
    build_unified_outcome_readmodel,
)


class PipelineEngine:

    def __init__(self, pair_membership_verifier=None):
        self.paper_db = PaperDatabase()
        self.price = CachePrice()
        self.cache = GeckoCache()
        self.pair_membership_verifier = (
            pair_membership_verifier
            or verify_pair_membership
        )
        self.scanner = GeckoScanner()
        self.last_scanner_refresh = {
            "state": "NOT_RUN",
            "rows": 0,
            "error": None,
        }
        self.last_cache_pruned = 0
        self.last_cycle_status = {
            "state": "NOT_RUN",
            "decisions": [],
        }
        self.filter = CacheFilter()
        self.ingress_gate = IngressGate()
        self.learning_outcome_feed = (
            RuntimeLearningOutcomeFeed(
                chain="bsc"
            )
        )
        self.counterfactual_store = (
            CounterfactualObservationStore()
        )

        self.manager = PaperManager(
            learning_feed=(
                self.learning_outcome_feed
            )
        )

        self.candidate_queue = CandidateAdmissionQueue(
            max_pending=MAX_PENDING_CANDIDATES,
            cooldown_seconds=RECENT_ANALYSIS_COOLDOWN_SECONDS,
        )
        self.conveyor = ConveyorLabeler()
        self.work_scheduler = WorkScheduler(
            max_workers=ANALYZER_WORKERS
        )
        self.intelligence = (
            RuntimeIntelligenceComposition()
        )

        self.native_market_flow = (
            RuntimeMarketFlowStore(
                require_membership_confirmation=True
            )
        )

        self.native_actor_intelligence = (
            RuntimeActorIntelligence(
                chain="bsc",
                wallet_writer=(
                    self.intelligence.update_wallet
                ),
                adversary_writer=(
                    self.intelligence.update_adversary
                ),
            )
        )

    def configure_native_market_flow(
        self,
        pair,
        token,
        quote_token,
    ):
        return self.native_market_flow.register_pair(
            pair,
            token,
            quote_token,
        )

    def native_wss_targets(self, max_pairs=256):
        normalized = normalize_source_rows(
            "geckoterminal",
            "bsc",
            self.cache.all(),
        )

        targets = []
        seen = set()

        classified = (
            self.ingress_gate.classify(
                candidate.to_dict()
            )
            for candidate in normalized["candidates"]
        )

        rows = [
            item["row"]
            for item in classified
            if item["lane"] == "ACTIVE"
            and item["row"].get("dex") == "pancakeswap_v2"
        ]

        rows.sort(
            key=lambda row: (
                float(row.get("buys_24h") or row.get("buys24") or 0),
                float(row.get("volume_24h") or row.get("volume24") or 0),
                float(row.get("liquidity") or 0),
            ),
            reverse=True,
        )

        for row in rows:
            pair = str(row.get("pool") or "").strip().lower()
            token = str(row.get("token") or "").strip().lower()
            quote = str(row.get("quote_token") or "").strip().lower()

            if not pair or not token or not quote or pair in seen:
                continue

            membership = self.pair_membership_verifier(
                pair,
                token,
                quote,
            )

            if membership.get("state") != "VERIFIED":
                continue

            seen.add(pair)
            targets.append({
                "pair": pair,
                "token": token,
                "quote_token": quote,
                "membership_verified": True,
            })

            if len(targets) >= max(1, int(max_pairs)):
                break

        return targets

    def confirm_native_market_flow(
        self,
        pair,
        token,
        quote_token,
    ):
        return self.native_market_flow.confirm_pair_membership(
            pair,
            token,
            quote_token,
        )

    async def on_native_event(
        self,
        event,
    ):
        market_result = (
            self.native_market_flow.observe_event(
                event
            )
        )

        actor_runtime = getattr(
            self,
            "native_actor_intelligence",
            None,
        )

        if actor_runtime is not None:
            await actor_runtime.observe_event(
                event,
                direction=(
                    market_result.get(
                        "direction",
                        "UNKNOWN",
                    )
                ),
            )

        return True

    async def on_native_retraction(
        self,
        event,
    ):
        self.native_market_flow.observe_retraction(
            event
        )

        actor_runtime = getattr(
            self,
            "native_actor_intelligence",
            None,
        )

        if actor_runtime is not None:
            await actor_runtime.observe_retraction(
                event
            )

        return True

    def refresh_open_position_prices(self, max_positions=30):
        positions = self.manager.db.open_positions()
        selected = positions[:max(1, int(max_positions))]

        pool_by_token = {}
        failed = 0

        for position in selected:
            pool = None
            raw_context = position.get(
                "opening_context_json"
            )

            if raw_context:
                try:
                    opening_context = json.loads(
                        raw_context
                    )
                    pool = (
                        opening_context.get(
                            "raw_signals",
                            {},
                        ).get("pool")
                    )
                except (
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ):
                    pool = None

            if not pool:
                pool = self.cache.pool_for_token(
                    position["token"]
                )

            if pool:
                pool_by_token[position["token"]] = pool
            else:
                failed += 1

        pools = list(dict.fromkeys(
            pool_by_token.values()
        ))

        if not pools:
            return {
                "state": "REFRESHED",
                "open_positions": len(positions),
                "refreshed": 0,
                "failed": failed,
                "requests": 0,
                "bounded": True,
            }

        try:
            pool_prices = getattr(
                self.scanner,
                "pool_prices",
                None,
            )

            if pool_prices is not None:
                prices = pool_prices(pools)
            else:
                prices = {
                    pool: self.scanner.pool_price(pool)
                    for pool in pools
                }

        except Exception:
            return {
                "state": "FAILED_USING_CACHE",
                "open_positions": len(positions),
                "refreshed": 0,
                "failed": failed + len(pools),
                "requests": 1,
                "bounded": True,
            }

        refreshed = 0

        for pool in pools:
            price = prices.get(pool.lower())

            if price is None:
                failed += 1
                continue

            if self.cache.update_pool_price(pool, price):
                refreshed += 1
            else:
                upsert = getattr(
                    self.cache,
                    "upsert_tracked_price",
                    None,
                )

                token = next(
                    (
                        token
                        for token, tracked_pool
                        in pool_by_token.items()
                        if tracked_pool == pool
                    ),
                    None,
                )

                if upsert is not None and token:
                    upsert(pool, token, price)
                    refreshed += 1
                else:
                    failed += 1

        return {
            "state": "REFRESHED",
            "open_positions": len(positions),
            "refreshed": refreshed,
            "failed": failed,
            "requests": 1,
            "bounded": True,
        }

    def _hybrid_exit_runtime_evidence(
        self,
        position,
    ):
        position = dict(position or {})

        token = position.get("token")
        pool = None
        candidate = {}

        raw_context = position.get(
            "opening_context_json"
        )

        if raw_context:
            try:
                opening_context = json.loads(
                    raw_context
                )

                if isinstance(
                    opening_context,
                    dict,
                ):
                    raw_signals = (
                        opening_context.get(
                            "raw_signals"
                        )
                        or {}
                    )

                    if isinstance(
                        raw_signals,
                        dict,
                    ):
                        candidate = dict(
                            raw_signals
                        )

                        pool = (
                            raw_signals.get(
                                "pool"
                            )
                        )

                    market_context = (
                        opening_context.get(
                            "market_context"
                        )
                        or {}
                    )

                    if isinstance(
                        market_context,
                        dict,
                    ):
                        for key in (
                            "liquidity",
                            "volume_24h",
                            "volume24",
                            "buys_24h",
                            "buys24",
                            "price_usd",
                        ):
                            if (
                                key
                                not in candidate
                                and key
                                in market_context
                            ):
                                candidate[key] = (
                                    market_context[
                                        key
                                    ]
                                )

            except (
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                pool = None
                candidate = {}

        if not pool and token:
            pool = self.cache.pool_for_token(
                token
            )

        if not pool:
            return None

        candidate.setdefault(
            "pool",
            pool,
        )

        runtime = getattr(
            self,
            "native_market_flow",
            None,
        )

        snapshot_fn = getattr(
            runtime,
            "snapshot",
            None,
        )

        if not callable(snapshot_fn):
            return None

        try:
            snapshot = snapshot_fn(
                pool,
                candidate=candidate,
            )
        except Exception:
            return None

        if not isinstance(
            snapshot,
            dict,
        ):
            return None

        market = (
            snapshot.get(
                "market_intelligence"
            )
            or {}
        )

        flow = (
            snapshot.get(
                "flow_intelligence"
            )
            or {}
        )

        market_ready = bool(
            isinstance(market, dict)
            and market.get(
                "evidence_ready"
            )
        )

        flow_ready = bool(
            isinstance(flow, dict)
            and flow.get(
                "evidence_ready"
            )
        )

        if not (
            market_ready
            or flow_ready
        ):
            return None

        # Preserve the existing runtime evidence contract.
        # Canonical semantic migration can overlay these fields
        # without breaking current consumers.
        signal_bundle = {}

        if market_ready:
            signal_bundle.update(
                market
            )

        if flow_ready:
            signal_bundle.update(
                flow
            )

        # Normalize semantic aliases already produced by the
        # native runtime. No new authority or external work.
        if signal_bundle.get(
            "liquidity_health"
        ) is None:
            market_quality = signal_bundle.get(
                "market_quality"
            )

            if isinstance(
                market_quality,
                dict,
            ):
                signal_bundle[
                    "liquidity_health"
                ] = market_quality.get(
                    "liquidity_state"
                )

        if signal_bundle.get(
            "price_impact_health"
        ) is None:
            price_impact = signal_bundle.get(
                "price_impact"
            )

            if isinstance(
                price_impact,
                dict,
            ):
                signal_bundle[
                    "price_impact_health"
                ] = price_impact.get(
                    "estimated_impact_context"
                )

        return {
            "state": snapshot.get(
                "state",
                "UNKNOWN",
            ),
            "signal_bundle": (
                signal_bundle
            ),
            "runtime_market_flow": (
                snapshot
            ),
            "source": snapshot.get(
                "source",
                "SCANNER_PLUS_NATIVE_WSS",
            ),
            "synthetic": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def process_positions(self):
        manager_db = getattr(
            self.manager,
            "db",
            None,
        )

        open_positions = getattr(
            manager_db,
            "open_positions",
            None,
        )

        # Production uses the durable DB adapter and
        # refreshes bounded prices before lifecycle
        # evaluation. DB-less legacy/test adapters keep
        # their historical process() contract.
        if callable(open_positions):
            self.refresh_open_position_prices()

        previous_evidence = getattr(
            self.manager,
            "hybrid_exit_evidence",
            None,
        )

        self.manager.hybrid_exit_evidence = (
            self._hybrid_exit_runtime_evidence
        )

        try:
            return self.manager.process()
        finally:
            self.manager.hybrid_exit_evidence = (
                previous_evidence
            )

    def run(
        self,
        token_address: str,
        market_context=None,
        operator_input=None,
    ):

        market_context = dict(
            market_context or {}
        )

        intelligence = getattr(
            self,
            "intelligence",
            None,
        )

        if intelligence is None:
            intelligence = (
                RuntimeIntelligenceComposition()
            )
            self.intelligence = intelligence

        intelligence_context = (
            intelligence.build(
                token_address,
                market_input=market_context.get(
                    "market_intelligence"
                ),
                flow_input=market_context.get(
                    "flow_intelligence"
                ),
                wallet_id=market_context.get(
                    "wallet_id"
                ),
                adversary_key=market_context.get(
                    "adversary_key"
                ),
            )
        )

        token_result = token_analyze(token_address)
        pair_result = pair_analyze(token_address)
        risk_result = risk_analyze(token_address)

        token = token_result.get("data", {})
        pair = pair_result.get("data", {})
        risk = risk_result.get("data", {})

        analyzer_status = {
            "token": {
                "status": (
                    "TOKEN_OK"
                    if token_result.get("success")
                    else "TOKEN_UNKNOWN"
                ),
                "error": token_result.get("error"),
            },
            "pair": {
                "status": (
                    "PAIR_OK"
                    if pair_result.get("success")
                    else "PAIR_UNKNOWN"
                ),
                "error": pair_result.get("error"),
            },
            "risk": {
                "status": (
                    "RISK_OK"
                    if risk_result.get("success")
                    else "RISK_UNKNOWN"
                ),
                "error": risk_result.get("error"),
            },
        }

        # Cheap/local risk gate first.
        risk_gate = _risk_gate.evaluate(
            risk
        )

        strategy = _strategy.evaluate(
            token,
            pair,
            risk,
        ).get("data", {})

        sellability_result = {
            "success": False,
            "source": "sellability",
            "error": None,
            "data": {},
        }

        # Deep external sellability check is NOT
        # run for every discovered candidate.
        #
        # Only a candidate already good enough
        # for PAPER_BUY pays this cost.
        if (
            not risk_gate["hard_block"]
            and strategy.get("decision")
            == "PAPER_BUY"
            and pair.get("exists") is True
            and pair.get("quote_ok") is True
        ):
            sellability_result = (
                sellability_analyze(
                    token_address,
                    pair=pair.get("pair"),
                )
            )

            if sellability_result.get(
                "success"
            ):
                risk.update(
                    sellability_result.get(
                        "data",
                        {},
                    )
                )

                # Re-evaluate only after receiving
                # real deep-risk evidence.
                risk_gate = (
                    _risk_gate.evaluate(
                        risk
                    )
                )

        trap_risk = _trap_risk.evaluate(
            risk
        )

        mev_risk = _mev_risk.evaluate(
            market_context
        )

        unified_score = (
            _unified_score.evaluate(
                strategy=strategy,
                risk_gate=risk_gate,
                trap_risk=trap_risk,
                mev_risk=mev_risk,
            )
        )

        unified_decision = (
            _unified_decision.evaluate(
                unified_score
            )
        )

        execution_context = (
            build_execution_context(
                market_context=market_context,
                risk=risk,
            )
        )

        execution_cost = (
            _execution_cost.evaluate(
                execution_context
            )
        )

        if risk_gate["hard_block"]:
            strategy["decision"] = "REJECT"
            strategy["risk"] = "HIGH"
            strategy["paper_trade"] = False

            reasons = strategy.setdefault(
                "reasons",
                [],
            )

            for reason in (
                risk_gate[
                    "hard_block_reasons"
                ]
            ):
                reasons.append(
                    f"HARD_BLOCK: {reason}"
                )

        decision = paper_admission_decision(
            strategy,
            unified_decision,
            risk_gate,
        )

        if sellability_result.get(
            "success"
        ):
            sellability_status = (
                "SELLABILITY_OK"
            )

        elif (
            strategy.get("decision")
            == "PAPER_BUY"
            and not risk_gate[
                "hard_block"
            ]
        ):
            sellability_status = (
                "SELLABILITY_UNKNOWN"
            )

        else:
            sellability_status = (
                "SELLABILITY_SKIPPED"
            )

        analyzer_status[
            "sellability"
        ] = {
            "status": (
                sellability_status
            ),
            "error": (
                sellability_result.get(
                    "error"
                )
            ),
        }

        paper = {}

        if decision == "PAPER_BUY":

            if self.paper_db.has_open_position(token_address):

                paper = {
                    "action": "SKIP",
                    "reason": "OPEN_POSITION_EXISTS",
                }

            else:

                try:
                    price = self.price.get_price(token_address)
                except Exception:
                    price = 0.0

                if price <= 0:

                    paper = {
                        "action": "SKIP",
                        "reason": "PRICE_UNAVAILABLE",
                    }

                else:

                    capital_row = self.paper_db.conn.execute(
                        '''
                        SELECT COALESCE(SUM(entry_amount_usdt), 0)
                        FROM paper_trades
                        WHERE status='OPEN'
                          AND paper_account_version='PAPER_10K_V2'
                        '''
                    ).fetchone()

                    capital_in_use = float(
                        capital_row[0] or 0.0
                    )

                    available_capital_usdt = max(
                        0.0,
                        PAPER_CAPITAL_USDT - capital_in_use,
                    )

                    mq = intelligence_context.get(
                        "market_quality"
                    ) or {}
                    fs = intelligence_context.get(
                        "flow_spread"
                    ) or {}

                    flow_momentum = fs.get("spread")
                    flow_acceleration = fs.get(
                        "acceleration"
                    )
                    liquidity_health = mq.get(
                        "liquidity_state"
                    )

                    if (
                        flow_momentum is None
                        and flow_acceleration is None
                        and not liquidity_health
                    ):
                        dynamic_sl = None
                        sl_distance_pct = max(
                            0.0001,
                            1.0 - SL_PRICE_MULTIPLIER,
                        )
                    else:
                        dynamic_sl = calculate_dynamic_sl(
                            flow_momentum=flow_momentum,
                            flow_acceleration=flow_acceleration,
                            liquidity_health=liquidity_health,
                        )
                        sl_distance_pct = dynamic_sl[
                            "sl_distance_pct"
                        ]

                    sizing = calculate_paper_position_size(
                        score=unified_score.get("score"),
                        confidence=unified_score.get("confidence"),
                        hard_block=risk_gate.get("hard_block"),
                        sellability=sellability_status,
                        available_capital_usdt=available_capital_usdt,
                        sl_distance_pct=sl_distance_pct,
                    )

                    entry_amount_usdt = float(
                        sizing["entry_amount_usdt"]
                    )

                    if entry_amount_usdt <= 0:
                        paper = {
                            "action": "SKIP",
                            "reason": sizing["sizing_reason"],
                        }
                        return {
                            "success": True,
                            "source": "pipeline",
                            "data": {
                                "paper": paper,
                            },
                        }

                    token_amount = entry_amount_usdt / price

                    entry_wallet_id = market_context.get(
                        "wallet_id"
                    )

                    opening_context = {
                        "captured_at_entry": True,
                        "actor_identity": {
                            "wallet_id": entry_wallet_id,
                            "actor_id": entry_wallet_id,
                            "identity_source": (
                                "TRANSACTION_FROM_ONLY"
                                if entry_wallet_id
                                else "UNKNOWN"
                            ),
                            "hindsight_reconstructed": False,
                        },
                        "historical_signal": "POSITIVE",
                        "historical_action": "ALLOW",
                        "entry_context_version": (
                            "PHASE13A_V1"
                        ),
                        "signal_attribution": (
                            build_entry_signal_attribution(
                                strategy_decision=(
                                    strategy.get(
                                        "decision"
                                    )
                                ),
                                unified_decision=(
                                    unified_decision.get(
                                        "decision"
                                    )
                                ),
                                hard_block=(
                                    risk_gate.get(
                                        "hard_block"
                                    )
                                ),
                                sellability_status=(
                                    analyzer_status[
                                        "sellability"
                                    ]["status"]
                                ),
                            )
                        ),
                        "exit_baseline": (
                            build_exit_baseline(
                                entry_price=price,
                                take_profit_price=(
                                    price
                                    * TP_PRICE_MULTIPLIER
                                ),
                                stop_loss_price=(
                                    price
                                    * SL_PRICE_MULTIPLIER
                                ),
                            )
                        ),
                        "raw_signals": {
                            "strategy_decision": (
                                strategy.get("decision")
                            ),
                            "unified_decision": (
                                unified_decision.get(
                                    "decision"
                                )
                            ),
                            "hard_block": bool(
                                risk_gate.get(
                                    "hard_block"
                                )
                            ),
                            "unified_score": (
                                unified_score.get("score")
                            ),
                            "unified_confidence": (
                                unified_score.get("confidence")
                            ),
                            "unified_coverage": (
                                unified_score.get("coverage")
                            ),
                            "sellability_status": (
                                analyzer_status[
                                    "sellability"
                                ]["status"]
                            ),
                            "pool": market_context.get(
                                "candidate_pool"
                            ),
                            "quote_token": market_context.get(
                                "candidate_quote_token"
                            ),
                            "runtime_context_only": (
                                intelligence_context.get(
                                    "context_only",
                                    True,
                                )
                            ),
                        },
                        "hindsight_reconstructed": False,
                        "decision_authority": False,
                        "live_authority": False,
                        "wallet_authority": False,
                        "execution_authority": False,
                    }

                    opening_context_json = json.dumps(
                        opening_context,
                        sort_keys=True,
                        separators=(",", ":"),
                    )

                    trade_row = {
                            "token": token_address,
                            "symbol": token.get("symbol", "?"),
                            "pool": market_context.get(
                                "candidate_pool"
                            ),

                            "entry_price": price,
                            "current_price": price,
                            "highest_price": price,
                            "lowest_price": price,

                            "tp_price": price * TP_PRICE_MULTIPLIER,
                            "sl_price": price * (1.0 - sl_distance_pct),

                            "amount_bnb": 0.0,
                            "token_amount": token_amount,

                            "paper_account_version": "PAPER_10K_V2",
                            "entry_amount_usdt": entry_amount_usdt,
                            "risk_amount_usdt": sizing["risk_amount_usdt"],
                            "capital_before_usdt": sizing["capital_before_usdt"],
                            "capital_after_entry_usdt": sizing["capital_after_entry_usdt"],
                            "position_size_pct": sizing["position_size_pct"],
                            "sizing_reason": sizing["sizing_reason"],

                            "gas_buy": DEFAULT_GAS_BUY,
                            "gas_sell": DEFAULT_GAS_SELL,
                            "swap_fee": DEFAULT_SWAP_FEE,

                            "buy_tax": DEFAULT_BUY_TAX,
                            "sell_tax": DEFAULT_SELL_TAX,

                            "slippage": DEFAULT_SLIPPAGE,
                            "mev": DEFAULT_MEV_COST,

                            "status": "OPEN",
                            "opening_context_json": (
                                opening_context_json
                            ),
                        }

                    bounded_insert = getattr(
                        self.paper_db,
                        "insert_if_below_open_limit",
                        None,
                    )

                    if bounded_insert is not None:
                        inserted = bounded_insert(
                            trade_row,
                            MAX_OPEN_PAPER_POSITIONS,
                        )
                    else:
                        inserted = (
                            self.paper_db.insert_if_no_open_position(
                                trade_row
                            )
                        )

                    if not inserted:
                        if self.paper_db.has_open_position(
                            token_address
                        ):
                            reason = "OPEN_POSITION_EXISTS"
                        else:
                            reason = "PAPER_POSITION_CAP_REACHED"

                        paper = {
                            "action": "SKIP",
                            "reason": reason,
                        }

                    else:
                        paper = {
                            "action": "PAPER_BUY",
                            "token": token_address,
                            "entry_price": price,
                            "token_amount": token_amount,
                            "amount_bnb": 0.0,
                            "entry_amount_usdt": entry_amount_usdt,
                            "risk_amount_usdt": sizing["risk_amount_usdt"],
                            "position_size_pct": sizing["position_size_pct"],
                            "paper_account_version": "PAPER_10K_V2",
                        }

        else:

            paper = {
                "action": decision,
            }

        tactical_truth = (
            build_tactical_truth(
                market_context=market_context,
                execution_cost=execution_cost,
                paper=paper,
                tp_multiplier=TP_PRICE_MULTIPLIER,
                sl_multiplier=SL_PRICE_MULTIPLIER,
            )
        )

        # phase14_operating_mode_runtime_binding
        operating_mode = build_operating_mode_readmodel()

        # Phase 14 bounded operator input binding.
        # Produces a request only. Never executes/signs.
        operator_command = {}

        if operator_input:
            raw_operator_input = dict(operator_input)

            operator_command = build_operator_command(
                source=raw_operator_input.get(
                    "source",
                    "PANEL_OPERATOR",
                ),
                raw_input=raw_operator_input.get(
                    "raw_input"
                ),
                intent=raw_operator_input.get(
                    "intent"
                ),
                token=(
                    raw_operator_input.get("token")
                    or token_address
                ),
                pool=(
                    raw_operator_input.get("pool")
                    or market_context.get(
                        "candidate_pool"
                    )
                ),
                chain=(
                    raw_operator_input.get("chain")
                    or market_context.get(
                        "chain",
                        "bsc",
                    )
                ),
                amount=raw_operator_input.get(
                    "amount"
                ),
                amount_unit=raw_operator_input.get(
                    "amount_unit"
                ),
                position_id=raw_operator_input.get(
                    "position_id"
                ),
                requested_mode=raw_operator_input.get(
                    "requested_mode",
                    "MANUAL",
                ),
                reason=raw_operator_input.get(
                    "reason"
                ),
                hard_block=bool(
                    risk_gate.get("hard_block")
                ),
                sellability=(
                    (
                        analyzer_status.get(
                            "sellability"
                        )
                        or {}
                    ).get("status")
                ),
                liquidity_usd=market_context.get(
                    "liquidity_usd"
                ),
                sl_tp_ready=bool(
                    tactical_truth.get(
                        "exit_plan"
                    )
                ),
                command_id=raw_operator_input.get(
                    "command_id"
                ),
            )


        # Phase 15D observation-only drift readmodel.
        #
        # Existing facts only:
        # - no new provider/RPC fetch
        # - no wallet/signing
        # - no execution
        # - no authority grant
        #
        # Missing evidence remains None.
        phase15_runtime_evidence = {
            "entry_price": market_context.get(
                "price_usd"
            ),
            "liquidity_usd": market_context.get(
                "liquidity_usd"
            ),
            "sellability": (
                analyzer_status.get(
                    "sellability",
                    {}
                ).get("status")
            ),
            "slippage_pct": execution_context.get(
                "slippage_pct"
            ),
            "gas_cost_usd": execution_context.get(
                "gas_cost_usd"
            ),
            "mev_cost_pct": execution_context.get(
                "mev_cost_pct"
            ),
            "quote_delay_ms": market_context.get(
                "quote_delay_ms"
            ),
            "execution_delay_ms": market_context.get(
                "execution_delay_ms"
            ),
            "execution_started_at": market_context.get(
                "execution_started_at"
            ),
            "execution_observed_at": market_context.get(
                "execution_observed_at"
            ),
        }

        simulation_drift = (
            build_phase15_drift_composition(
                paper_position=paper,
                runtime_evidence=(
                    phase15_runtime_evidence
                ),
            )
        )

        command_center = (
            build_command_center_readmodel(
                candidate={
                    "token": token_address,
                    "pool": market_context.get(
                        "candidate_pool"
                    ),
                    "chain": market_context.get(
                        "chain",
                        "bsc",
                    ),
                    "liquidity": market_context.get(
                        "liquidity_usd"
                    ),
                },
                pipeline_data={
                    "strategy": strategy,
                    "unified_score": unified_score,
                    "unified_decision": unified_decision,
                    "risk_gate": risk_gate,
                    "paper": paper,
                    "analyzer_status": analyzer_status,
                    "market_context": market_context,
                    "runtime_intelligence": (
                        intelligence_context
                    ),
                    "intelligence": (
                        intelligence_context
                    ),
                    "execution_cost": execution_cost,
                    "entry_plan": tactical_truth.get(
                        "entry_plan"
                    ),
                    "exit_plan": tactical_truth.get(
                        "exit_plan"
                    ),
                    "risk_reward": tactical_truth.get(
                        "risk_reward"
                    ),
                    "expected_pnl": tactical_truth.get(
                        "expected_pnl"
                    ),
                    "operating_mode": operating_mode,
                    "operator_command": operator_command,
                    "simulation_drift": simulation_drift,
                },
            )
        )

        return {
            "success": True,
            "source": "pipeline",
            "data": {
                "token": token,
                "pair": pair,
                "risk": risk,
                "risk_gate": risk_gate,
                "trap_risk": trap_risk,
                "mev_risk": mev_risk,
                "unified_score": unified_score,
                "unified_decision": unified_decision,
                "paper_admission_decision": decision,
                "execution_context": execution_context,
                "execution_cost": execution_cost,
                "market_context": market_context,
                "runtime_intelligence": (
                    intelligence_context
                ),
                "analyzer_status": analyzer_status,
                "strategy": strategy,
                "paper": paper,
                "tactical_truth": tactical_truth,
                "operating_mode": operating_mode,
                "operator_command": operator_command,
                "simulation_drift": simulation_drift,
                "command_center": command_center,
            },
        }

    def observe_counterfactual_candidate(
        self,
        row,
        summary,
        *,
        now=None,
    ):
        store = getattr(
            self,
            "counterfactual_store",
            None,
        )

        if store is None:
            store = CounterfactualObservationStore()
            self.counterfactual_store = store

        token = row.get("token")
        pool = row.get("pool")
        price = row.get("price_usd")

        evaluation = store.observe(
            token=token,
            current_price=price,
            evaluated_at=now,
        )

        action = summary.get("paper")

        if action == "WATCH":
            signal_state = "POSITIVE"
            candidate_action = "DOWNGRADE"

        elif action == "REJECT":
            signal_state = "NEGATIVE"
            candidate_action = "BLOCK"

        else:
            return {
                "evaluation": evaluation,
                "record": {
                    "state": "NOT_ELIGIBLE",
                    "stored": False,
                },
                "status": store.status(),
            }

        record = store.record(
            token=token,
            pool=pool,
            entry_price=price,
            signal_state=signal_state,
            candidate_action=candidate_action,
            observed_at=now,
            context={
                "strategy": summary.get(
                    "strategy"
                ),
                "unified": summary.get(
                    "unified"
                ),
                "paper": action,
                "reason": summary.get(
                    "reason"
                ),
                "hard_block": bool(
                    summary.get("hard_block")
                ),
                "score": summary.get("score"),
                "confidence": summary.get(
                    "confidence"
                ),
                "sellability": summary.get(
                    "sellability"
                ),
                "hindsight_reconstructed": False,
            },
        )

        return {
            "evaluation": evaluation,
            "record": record,
            "status": store.status(),
        }

    def unified_outcome_snapshot(self):
        paper_feed = getattr(
            self,
            "learning_outcome_feed",
            None,
        )
        counterfactual_store = getattr(
            self,
            "counterfactual_store",
            None,
        )

        paper_events = (
            paper_feed.event_snapshot()
            if paper_feed is not None
            else []
        )

        counterfactual_events = (
            counterfactual_store.outcome_snapshot()
            if counterfactual_store is not None
            else []
        )

        return build_unified_outcome_readmodel(
            paper_events=paper_events,
            counterfactual_events=(
                counterfactual_events
            ),
            min_paper_samples=20,
            min_counterfactual_samples=20,
        )

    def refresh_candidate_cache(self):
        scanner = getattr(
            self,
            "scanner",
            None,
        )

        if scanner is None:
            result = {
                "state": "DISABLED",
                "rows": 0,
                "error": None,
            }
            self.last_scanner_refresh = result
            return result

        rows = scanner.scan()

        for row in rows:
            self.cache.replace(row)

        self.last_cache_pruned = 0
        prune = getattr(
            self.cache,
            "prune_except",
            None,
        )

        if rows and prune is not None:
            preserve_tokens = []
            manager = getattr(self, "manager", None)
            manager_db = getattr(manager, "db", None)
            open_reader = getattr(
                manager_db,
                "open_positions",
                None,
            )

            if open_reader is not None:
                preserve_tokens = [
                    position["token"]
                    for position in open_reader()
                ]

            self.last_cache_pruned = prune(
                [
                    row["pool"]
                    for row in rows
                    if row.get("pool")
                ],
                preserve_tokens=preserve_tokens,
            )

        result = {
            "state": "REFRESHED",
            "rows": len(rows),
            "error": None,
        }

        self.last_scanner_refresh = result
        return result

    def run_cycle(self):

        try:
            self.refresh_candidate_cache()
        except Exception as exc:
            self.last_scanner_refresh = {
                "state": "FAILED_USING_CACHE",
                "rows": 0,
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }

            logger.warning(
                "Scanner refresh failed; using cache: %s",
                self.last_scanner_refresh["error"],
            )

        rows = self.cache.all()

        normalized_result = normalize_source_rows(
            "geckoterminal",
            "bsc",
            rows,
        )

        rows = [
            candidate.to_dict()
            for candidate
            in normalized_result["candidates"]
        ]

        if hasattr(self, "ingress_gate"):
            ingress = self.ingress_gate.classify_many(
                rows
            )

            candidates = ingress["active"]
            ingress_stats = ingress["stats"]

        elif hasattr(self.filter, "filter_all"):
            candidates = self.filter.filter_all(rows)

            ingress_stats = {
                "input": len(rows),
                "active": len(candidates),
                "deferred": 0,
                "dropped": (
                    len(rows)
                    - len(candidates)
                ),
            }

        else:
            candidates = self.filter.filter(rows)

            ingress_stats = {
                "input": len(rows),
                "active": len(candidates),
                "deferred": 0,
                "dropped": (
                    len(rows)
                    - len(candidates)
                ),
            }

        if not hasattr(self, "candidate_queue"):
            self.candidate_queue = CandidateAdmissionQueue(
                max_pending=MAX_PENDING_CANDIDATES,
                cooldown_seconds=RECENT_ANALYSIS_COOLDOWN_SECONDS,
            )

        if hasattr(self, "conveyor"):
            conveyor_result = self.conveyor.label_many(
                candidates
            )

            candidates = conveyor_result["rows"]
            conveyor_stats = conveyor_result["stats"]
        else:
            conveyor_stats = {
                "warm": 0,
                "partial": 0,
                "cold": len(candidates),
            }

        self.candidate_queue.enqueue_many(candidates)

        if not hasattr(self, "work_scheduler"):
            self.work_scheduler = WorkScheduler(
                max_workers=ANALYZER_WORKERS
            )

        queue_stats = self.candidate_queue.stats()

        logger.info(
            (
                "Cache=%s Active=%s Deferred=%s "
                "Dropped=%s Warm=%s Partial=%s Cold=%s "
                "PendingBefore=%s "
                "Duplicates=%s CooldownSkipped=%s"
            ),
            len(rows),
            ingress_stats["active"],
            ingress_stats["deferred"],
            ingress_stats["dropped"],
            conveyor_stats["warm"],
            conveyor_stats["partial"],
            conveyor_stats["cold"],
            queue_stats["pending"],
            queue_stats["duplicates_collapsed"],
            queue_stats["cooldown_skipped"],
        )

        decision_rows = []
        counterfactual_rows = []
        decision_lock = threading.Lock()

        def process_row(row):
            token = row["token"]

            runtime_feed = getattr(
                self,
                "native_market_flow",
                None,
            )

            confirm_pair = getattr(
                runtime_feed,
                "confirm_pair_membership",
                None,
            )

            if confirm_pair is not None:
                confirm_pair(
                    row.get("pool"),
                    row.get("token"),
                    row.get("quote_token"),
                )

            market_context = (
                build_market_context(
                    row,
                    runtime_feed=getattr(
                        self,
                        "native_market_flow",
                        None,
                    ),
                )
            )

            market_context["candidate_pool"] = row.get(
                "pool"
            )
            market_context["candidate_quote_token"] = row.get(
                "quote_token"
            )

            actor_runtime = getattr(
                self,
                "native_actor_intelligence",
                None,
            )

            if actor_runtime is not None:
                actor_snapshot = (
                    actor_runtime.snapshot(
                        row.get("pool")
                    )
                )

                if (
                    actor_snapshot.get(
                        "state"
                    )
                    == "READY"
                ):
                    market_context[
                        "wallet_id"
                    ] = actor_snapshot[
                        "wallet_id"
                    ]

                    market_context[
                        "adversary_key"
                    ] = actor_snapshot[
                        "adversary_key"
                    ]

                    market_context[
                        "runtime_actor"
                    ] = actor_snapshot

            try:
                result = self.run(
                    token,
                    market_context=(
                        market_context
                    ),
                )

                data = result.get("data", {})
                strategy = data.get("strategy") or {}
                unified = data.get("unified_decision") or {}
                paper = data.get("paper") or {}
                score = data.get("unified_score") or {}
                risk_gate = data.get("risk_gate") or {}
                analyzer_status = (
                    data.get("analyzer_status") or {}
                )
                command_center = (
                    data.get("command_center") or {}
                )

                summary = {
                    "token": token,
                    "pool": row.get("pool"),
                    "strategy": strategy.get("decision"),
                    "unified": unified.get("decision"),
                    "paper": paper.get("action"),
                    "reason": paper.get("reason"),
                    "hard_block": bool(
                        risk_gate.get("hard_block")
                    ),
                    "score": score.get("score"),
                    "confidence": score.get("confidence"),
                    "sellability": (
                        analyzer_status.get(
                            "sellability",
                            {},
                        ).get("status")
                    ),
                    "command_center": command_center,
                }

                counterfactual = (
                    self.observe_counterfactual_candidate(
                        row,
                        summary,
                    )
                )

                with decision_lock:
                    if len(decision_rows) < 100:
                        decision_rows.append(summary)

                    evaluation = counterfactual[
                        "evaluation"
                    ]

                    if (
                        evaluation.get("state")
                        == "EVALUATED"
                        and len(counterfactual_rows)
                        < 100
                    ):
                        counterfactual_rows.append(
                            evaluation
                        )

                logger.info(
                    (
                        "Candidate token=%s pool=%s "
                        "strategy=%s unified=%s "
                        "paper=%s reason=%s "
                        "hard_block=%s score=%s "
                        "confidence=%s sellability=%s"
                    ),
                    summary["token"],
                    summary["pool"],
                    summary["strategy"],
                    summary["unified"],
                    summary["paper"],
                    summary["reason"],
                    summary["hard_block"],
                    summary["score"],
                    summary["confidence"],
                    summary["sellability"],
                )

                if not result.get("success"):
                    logger.warning(
                        "Pipeline failed: %s",
                        token,
                    )

            except Exception:
                logger.exception(
                    "Pipeline exception: %s",
                    token,
                )
                raise

            finally:
                self.candidate_queue.mark_analyzed(
                    token,
                    chain=row.get("chain", "bsc"),
                )

        scheduler_result = self.work_scheduler.process_queue(
            self.candidate_queue,
            process_row,
        )

        manager_results = []
        manager_error = None

        try:
            # Scanner cycle must use the same position
            # lifecycle entrypoint as the scheduled
            # paper-manager job. This guarantees that
            # bounded open-position prices are refreshed
            # before TP/SL/trailing evaluation.
            manager_results = (
                self.process_positions()
                or []
            )
        except Exception as exc:
            manager_error = (
                f"{type(exc).__name__}: {exc}"
            )

            logger.exception(
                "Paper manager exception"
            )

        paper_counts = {}

        for row in decision_rows:
            action = row.get("paper") or "UNKNOWN"
            paper_counts[action] = (
                paper_counts.get(action, 0)
                + 1
            )

        counterfactual_counts = {}

        for row in counterfactual_rows:
            outcome = row.get(
                "outcome_class",
                "UNKNOWN",
            )
            counterfactual_counts[outcome] = (
                counterfactual_counts.get(
                    outcome,
                    0,
                )
                + 1
            )

        counterfactual_store = getattr(
            self,
            "counterfactual_store",
            None,
        )

        if counterfactual_store is None:
            counterfactual_store = (
                CounterfactualObservationStore()
            )
            self.counterfactual_store = (
                counterfactual_store
            )

        counterfactual_status = (
            counterfactual_store.status()
        )

        unified_outcome = (
            self.unified_outcome_snapshot()
        )

        status = {
            "state": (
                "READY"
                if scheduler_result.get("failed", 0) == 0
                and manager_error is None
                else "DEGRADED"
            ),
            "scanner": dict(
                self.last_scanner_refresh
            ),
            "ingress": dict(ingress_stats),
            "queue": dict(queue_stats),
            "scheduler": scheduler_result,
            "decision_count": len(decision_rows),
            "paper_actions": paper_counts,
            "decisions": decision_rows,
            "unified_outcome": unified_outcome,
            "counterfactual": {
                "evaluated_count": len(
                    counterfactual_rows
                ),
                "outcome_counts": (
                    counterfactual_counts
                ),
                "results": counterfactual_rows,
                "store": counterfactual_status,
                "cumulative_outcome_counts": (
                    counterfactual_status[
                        "outcome_counts"
                    ]
                ),
                "bounded": True,
                "provider_call": False,
                "decision_authority": False,
                "execution_authority": False,
            },
            "paper_manager_count": len(
                manager_results
            ),
            "paper_manager_error": manager_error,
            "decision_authority": False,
            "live_authority": False,
            "execution_authority": False,
        }

        self.last_cycle_status = status

        logger.info(
            (
                "Cycle state=%s decisions=%s "
                "paper_actions=%s manager=%s "
                "counterfactual=%s cumulative=%s "
                "observed=%s unified=%s "
                "paper_samples=%s "
                "counterfactual_samples=%s"
            ),
            status["state"],
            status["decision_count"],
            status["paper_actions"],
            status["paper_manager_count"],
            status["counterfactual"][
                "outcome_counts"
            ],
            status["counterfactual"][
                "cumulative_outcome_counts"
            ],
            status["counterfactual"][
                "store"
            ]["size"],
            status["unified_outcome"]["state"],
            status["unified_outcome"][
                "paper_sample_count"
            ],
            status["unified_outcome"][
                "counterfactual_sample_count"
            ],
        )

        return status

