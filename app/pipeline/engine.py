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
    paper_available_capital_usdt,
)
from app.strategy.engine import StrategyEngine
from app.strategy.unified_score import UnifiedScoreEngine
from app.strategy.decision import UnifiedDecisionEngine
from app.strategy.execution_cost import ExecutionCostEngine
from app.strategy.mathematical_trade_plan import build_trade_plan

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
from app.dex.flow_spread import flow_spread
from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.scanner.adapters.source_router import normalize_source_rows
from app.scanner.gecko_scanner import GeckoScanner

from app.config.scanner import (
    ANALYZER_WORKERS,
    MAX_PENDING_CANDIDATES,
    RECENT_ANALYSIS_COOLDOWN_SECONDS,
)

from app.config.trading import (
    MAX_OPEN_PAPER_POSITIONS,
)

from app.strategy.mathematical_trade_plan import initial_net_risk_usdt

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



# CANONICAL_RUNTIME_MATH_EVIDENCE
#
# Mathematical paper admission must use measured runtime evidence.
# Missing evidence stays UNKNOWN; no gate is relaxed and no value is
# fabricated. Price history and liquidity persistence below are built
# only from observations actually seen by this runtime.

_RUNTIME_PRICE_HISTORY = {}

# Candidates that have already passed empirical sizing but still need
# additional real price movement observations are retained separately
# from scanner discovery. This does not grant admission authority.
_RUNTIME_OBSERVATION_WATCH = {}
_RUNTIME_OBSERVATION_WATCH_MAX = 30
_RUNTIME_OBSERVATION_WATCH_LOCK = threading.Lock()


def _runtime_watch_candidate(
    token_address,
    pool,
    *,
    enabled,
):
    token_key = str(
        token_address or ""
    ).strip().lower()

    pool_key = str(
        pool or ""
    ).strip().lower()

    with _RUNTIME_OBSERVATION_WATCH_LOCK:
        if (
            not enabled
            or not token_key
            or not pool_key
        ):
            if token_key:
                _RUNTIME_OBSERVATION_WATCH.pop(
                    token_key,
                    None,
                )

            return False

        # Reinsert so the dict also behaves as a simple
        # bounded least-recently-qualified watch set.
        _RUNTIME_OBSERVATION_WATCH.pop(
            token_key,
            None,
        )

        while (
            len(_RUNTIME_OBSERVATION_WATCH)
            >= _RUNTIME_OBSERVATION_WATCH_MAX
        ):
            oldest = next(
                iter(_RUNTIME_OBSERVATION_WATCH)
            )

            _RUNTIME_OBSERVATION_WATCH.pop(
                oldest,
                None,
            )

        _RUNTIME_OBSERVATION_WATCH[
            token_key
        ] = pool_key

    return True


def _runtime_observation_watch_snapshot():
    with _RUNTIME_OBSERVATION_WATCH_LOCK:
        return dict(
            _RUNTIME_OBSERVATION_WATCH
        )


def _runtime_should_watch_movement(
    block_reason,
    plan_blockers,
):
    """
    Observation authority only.

    A mathematical PAPER_BUY candidate may remain in
    the bounded observation set whenever actual market
    movement is still insufficient. Other blockers stay
    fully effective and can continue to prevent entry.
    """
    return (
        block_reason
        == "PLAN_BLOCKED"
        and (
            "EMPIRICAL_MOVEMENT_INSUFFICIENT"
            in set(
                plan_blockers
                or ()
            )
        )
    )


def _runtime_positive_number(value):
    import math

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number) or number <= 0:
        return None

    return number


def _runtime_walk_evidence(value):
    if isinstance(value, dict):
        yield value

        for nested in value.values():
            yield from _runtime_walk_evidence(nested)

    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _runtime_walk_evidence(nested)


def _runtime_find_number(sources, keys):
    wanted = {
        str(key).lower()
        for key in keys
    }

    for source in sources:
        for mapping in _runtime_walk_evidence(source):
            for key, value in mapping.items():
                if str(key).lower() not in wanted:
                    continue

                number = _runtime_positive_number(value)

                if number is not None:
                    return number, str(key)

    return None, None


def _runtime_fraction(value):
    number = _runtime_positive_number(value)

    if number is None:
        return None

    if number > 1.0:
        if number <= 100.0:
            number = number / 100.0
        else:
            return None

    return min(1.0, number)


def _runtime_find_fraction(sources):
    direct_keys = {
        "lp_protected_fraction",
        "lp_locked_fraction",
        "lp_burned_fraction",
        "locked_lp_fraction",
        "burned_lp_fraction",
        "liquidity_locked_fraction",
    }

    pct_keys = {
        "lp_locked_pct",
        "lp_burned_pct",
        "locked_lp_pct",
        "burned_lp_pct",
        "liquidity_locked_pct",
        "lp_locked_percentage",
        "lp_burned_percentage",
    }

    fractions = []

    for source in sources:
        for mapping in _runtime_walk_evidence(source):
            for key, value in mapping.items():
                normalized = str(key).lower()

                if normalized in direct_keys:
                    fraction = _runtime_fraction(value)

                    if fraction is not None:
                        fractions.append(
                            (fraction, str(key))
                        )

                elif normalized in pct_keys:
                    number = _runtime_positive_number(value)

                    if number is not None and number <= 100.0:
                        fractions.append(
                            (
                                min(1.0, number / 100.0),
                                str(key),
                            )
                        )

    if not fractions:
        return None, None

    # Multiple independent evidence fields can use different names.
    # We do not add them because overlap may be unknown; taking the
    # strongest individually verified fraction avoids double counting.
    return max(
        fractions,
        key=lambda item: item[0],
    )


def _runtime_math_evidence(
    *,
    token_address,
    price,
    upstream_price_series,
    exit_evidence,
    lp_evidence,
    market_context,
    sellability_data,
):
    token_key = str(
        token_address or ""
    ).lower()

    current_price = _runtime_positive_number(price)

    history = _RUNTIME_PRICE_HISTORY.setdefault(
        token_key,
        [],
    )

    # Seed once from a real upstream series when one exists.
    if not history:
        for item in upstream_price_series or []:
            observed = _runtime_positive_number(item)

            if observed is not None:
                history.append(observed)

    # Every runtime cycle is an actual observation. Equal prices are
    # retained because a zero return is still a measured return.
    if current_price is not None:
        history.append(current_price)

    if len(history) > 64:
        del history[:-64]

    if len(_RUNTIME_PRICE_HISTORY) > 2048:
        oldest_key = next(iter(_RUNTIME_PRICE_HISTORY))

        if oldest_key != token_key:
            _RUNTIME_PRICE_HISTORY.pop(
                oldest_key,
                None,
            )

    sources = (
        exit_evidence or {},
        lp_evidence or {},
        market_context or {},
        sellability_data or {},
    )

    quote_reserve, quote_source = _runtime_find_number(
        sources,
        {
            "quote_reserve_usd",
            "quote_reserve_value_usd",
            "reserve_quote_usd",
            "quote_liquidity_usd",
            "quote_side_usd",
        },
    )

    # Gecko/AMM normalized data commonly exposes total two-asset
    # pool reserve in USD. When a concrete quote token and pool are
    # known, the pool spot-price identity makes either side one half
    # of total reserve value for a constant-product pair.
    if quote_reserve is None:
        total_reserve, total_source = _runtime_find_number(
            sources,
            {
                "reserve_in_usd",
                "total_reserve_usd",
                "total_liquidity_usd",
                "pool_liquidity_usd",
                "liquidity_usd",
            },
        )

        quote_token = (
            (market_context or {}).get(
                "candidate_quote_token"
            )
        )

        candidate_pool = (
            (market_context or {}).get(
                "candidate_pool"
            )
        )

        if (
            total_reserve is not None
            and quote_token
            and candidate_pool
        ):
            quote_reserve = (
                total_reserve / 2.0
            )
            quote_source = (
                f"{total_source}:TWO_ASSET_POOL_HALF"
            )

    # Only explicit LP-security evidence may
    # establish protected liquidity.
    #
    # Repeated reserve observations prove that
    # liquidity existed. They do not prove that
    # liquidity cannot be withdrawn.
    protected, protected_source = (
        _runtime_find_fraction(
            (
                lp_evidence or {},
            )
        )
    )

    return {
        "price_series": list(history),
        "quote_reserve_usd": quote_reserve,
        "quote_reserve_source": quote_source,
        "lp_protected_fraction": protected,
        "lp_protection_source": protected_source,
    }


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

        # Native WSS belongs to the observation plane.
        #
        # Do not wait for ingress/admission to mark a pool ACTIVE
        # before collecting its real market-flow evidence. Decision
        # admission remains unchanged later in run_cycle().
        #
        # The scanner/cache universe is already bounded, and the
        # membership verifier below still validates every WSS target.
        rows = [
            row
            for row in (
                candidate.to_dict()
                for candidate
                in normalized["candidates"]
            )
            if row.get("dex") == "pancakeswap_v2"
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

    def wait_for_native_market_evidence(
        self,
        pairs,
        *,
        timeout=10.0,
    ):
        runtime = getattr(
            self,
            "native_market_flow",
            None,
        )

        waiter = getattr(
            runtime,
            "wait_for_market_evidence",
            None,
        )

        if waiter is None:
            return {
                "state": "UNAVAILABLE",
                "requested": 0,
                "ready": 0,
                "pending": 0,
                "decision_authority": False,
                "execution_authority": False,
            }

        return waiter(
            pairs,
            timeout=timeout,
        )

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

            # Bind native runtime directional measurements into
            # the canonical adaptive-exit semantics.  This does
            # not invent percentages or thresholds: it reuses the
            # existing flow transformer and preserves its
            # freshness / complete-coverage contract.
            canonical_flow = flow_spread(
                flow.get("buy_flow"),
                flow.get("sell_flow"),
                prev_spread=flow.get(
                    "prev_spread"
                ),
                prev_velocity=flow.get(
                    "prev_velocity"
                ),
                freshness=flow.get(
                    "freshness",
                    "UNKNOWN",
                ),
                coverage=flow.get(
                    "coverage",
                    0.0,
                ),
            )

            if (
                canonical_flow.get("state")
                == "READY"
            ):
                buy_flow = canonical_flow.get(
                    "buy_flow"
                )
                sell_flow = canonical_flow.get(
                    "sell_flow"
                )
                total_flow = (
                    (buy_flow or 0.0)
                    + (sell_flow or 0.0)
                )

                if total_flow > 0:
                    signal_bundle[
                        "flow_momentum"
                    ] = (
                        canonical_flow["spread"]
                        / total_flow
                    )

                acceleration = (
                    canonical_flow.get(
                        "acceleration"
                    )
                )

                if (
                    acceleration is not None
                    and total_flow > 0
                ):
                    signal_bundle[
                        "flow_acceleration"
                    ] = (
                        acceleration
                        / total_flow
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

        sellability_attempted = False

        # Deep external sellability check is NOT
        # run for every discovered candidate.
        #
        # Only a candidate already good enough
        # for PAPER_BUY pays this cost.
        if (
            not risk_gate["hard_block"]
            and pair.get("exists") is True
            and pair.get("quote_ok") is True
        ):
            sellability_attempted = True

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

        sellability_data = (
            sellability_result.get("data") or {}
        )
        sellable = sellability_data.get(
            "sellable"
        )

        if (
            sellability_result.get("success")
            and sellable is True
        ):
            sellability_status = (
                "SELLABILITY_OK"
            )
        elif (
            sellability_result.get("success")
            and sellable is False
        ):
            sellability_status = (
                "SELLABILITY_FAIL"
            )
        elif (
            sellability_attempted
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

        decision = paper_admission_decision(
            strategy,
            unified_decision,
            risk_gate,
            sellability_status=(
                sellability_status
            ),
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

        # Mathematical planning uses canonical local
        # onchain evidence even when an external sellability
        # provider returns UNKNOWN.
        local_math_evidence = (
            risk_gate.get("local_evidence")
            or risk.get("local_evidence")
            or sellability_data.get("local_evidence")
            or {}
        )

        local_math_exit = (
            local_math_evidence.get(
                "exit_feasibility"
            )
            or {}
        )

        local_math_price_series = list(
            local_math_exit.get(
                "spot_price_series_usd"
            )
            or []
        )

        mathematical_plan = None
        paper = {}

        if decision == "PAPER_BUY":

            if self.paper_db.has_open_position(
                token_address
            ):
                paper = {
                    "action": "SKIP",
                    "reason": "OPEN_POSITION_EXISTS",
                }

            else:
                try:
                    price = (
                        self.price.get_price(
                            token_address
                        )
                    )
                except Exception:
                    price = 0.0

                # Cache absence is not evidence of
                # price absence. Use the latest price already
                # measured from verified pair reserves.
                if (
                    (
                        price is None
                        or price <= 0
                    )
                    and local_math_price_series
                ):
                    try:
                        price = float(
                            local_math_price_series[-1]
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        price = 0.0

                # Propagate measured facts to downstream
                # readmodels without inventing values.
                if (
                    price is not None
                    and price > 0
                    and market_context.get(
                        "price_usd"
                    ) is None
                ):
                    market_context[
                        "price_usd"
                    ] = price

                measured_liquidity = (
                    local_math_exit.get(
                        "liquidity_usd_estimate"
                    )
                )

                try:
                    measured_liquidity = (
                        float(measured_liquidity)
                        if measured_liquidity is not None
                        else None
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    measured_liquidity = None

                if (
                    measured_liquidity is not None
                    and measured_liquidity > 0
                    and market_context.get(
                        "liquidity_usd"
                    ) in (
                        None,
                        0,
                        0.0,
                    )
                ):
                    market_context[
                        "liquidity_usd"
                    ] = measured_liquidity

                if (
                    price is None
                    or price <= 0
                ):
                    paper = {
                        "action": "WATCH",
                        "reason": "PRICE_UNAVAILABLE",
                    }

                else:
                    available_capital_usdt = (
                        paper_available_capital_usdt(
                            self.paper_db.conn,
                            PAPER_CAPITAL_USDT,
                        )
                    )

                    local_evidence = (
                        local_math_evidence
                    )

                    lp_evidence = (
                        local_evidence.get(
                            "lp_security"
                        )
                        or {}
                    )

                    exit_evidence = (
                        local_evidence.get(
                            "exit_feasibility"
                        )
                        or {}
                    )

                    price_series = list(
                        exit_evidence.get(
                            "spot_price_series_usd"
                        )
                        or []
                    )

                    if (
                        price > 0
                        and (
                            not price_series
                            or (
                                price_series[-1]
                                != price
                            )
                        )
                    ):
                        price_series.append(
                            price
                        )

                    runtime_math_evidence = (
                        _runtime_math_evidence(
                            token_address=token_address,
                            price=price,
                            upstream_price_series=(
                                price_series
                            ),
                            exit_evidence=(
                                exit_evidence
                            ),
                            lp_evidence=(
                                lp_evidence
                            ),
                            market_context=(
                                market_context
                            ),
                            sellability_data=(
                                sellability_data
                            ),
                        )
                    )

                    price_series = (
                        runtime_math_evidence[
                            "price_series"
                        ]
                    )

                    exit_evidence = dict(
                        exit_evidence or {}
                    )

                    lp_evidence = dict(
                        lp_evidence or {}
                    )

                    if (
                        exit_evidence.get(
                            "quote_reserve_usd"
                        )
                        is None
                        and runtime_math_evidence.get(
                            "quote_reserve_usd"
                        )
                        is not None
                    ):
                        exit_evidence[
                            "quote_reserve_usd"
                        ] = runtime_math_evidence[
                            "quote_reserve_usd"
                        ]

                        exit_evidence[
                            "quote_reserve_source"
                        ] = runtime_math_evidence[
                            "quote_reserve_source"
                        ]

                    if (
                        lp_evidence.get(
                            "lp_protected_fraction"
                        )
                        is None
                        and runtime_math_evidence.get(
                            "lp_protected_fraction"
                        )
                        is not None
                    ):
                        lp_evidence[
                            "lp_protected_fraction"
                        ] = runtime_math_evidence[
                            "lp_protected_fraction"
                        ]

                        lp_evidence[
                            "lp_protection_source"
                        ] = runtime_math_evidence[
                            "lp_protection_source"
                        ]

                    mathematical_plan = (
                        build_trade_plan(
                            entry_price=price,

                            available_capital_usdt=(
                                available_capital_usdt
                            ),

                            price_series=(
                                price_series
                            ),

                            quote_reserve_usd=(
                                exit_evidence.get(
                                    "quote_reserve_usd"
                                )
                            ),

                            lp_protected_fraction=(
                                lp_evidence.get(
                                    "lp_protected_fraction"
                                )
                            ),

                            sellability_status=(
                                sellability_status
                            ),

                            hard_block=bool(
                                risk_gate.get(
                                    "hard_block"
                                )
                            ),

                            sellability_data=(
                                sellability_data
                            ),

                            exit_evidence=(
                                exit_evidence
                            ),

                            market_context={
                                "market_intelligence": (
                                    market_context.get(
                                        "market_intelligence"
                                    )
                                ),

                                "flow_intelligence": (
                                    market_context.get(
                                        "flow_intelligence"
                                    )
                                ),

                                "runtime_intelligence": (
                                    intelligence_context
                                ),
                            },
                        )
                    )

                    sizing = (
                        calculate_paper_position_size(
                            mathematical_plan=(
                                mathematical_plan
                            ),

                            available_capital_usdt=(
                                available_capital_usdt
                            ),
                        )
                    )

                    entry_amount_usdt = float(
                        sizing.get(
                            "entry_amount_usdt",
                            0.0,
                        )
                    )

                    # CANONICAL_PAPER_EXECUTION_INVENTORY_V1
                    token_amount = (
                        entry_amount_usdt
                        / float(price)
                        if (
                            entry_amount_usdt > 0
                            and float(price) > 0
                        )
                        else 0.0
                    )

                    plan_blockers = sorted(
                        {
                            str(value)
                            for value in (
                                mathematical_plan.get(
                                    "blockers"
                                )
                                or []
                            )
                        }
                    )

                    plan_unknowns = sorted(
                        {
                            str(value)
                            for value in (
                                mathematical_plan.get(
                                    "unknowns"
                                )
                                or []
                            )
                        }
                    )

                    sizing_blockers = sorted(
                        {
                            str(value)
                            for value in (
                                sizing.get(
                                    "blockers"
                                )
                                or []
                            )
                        }
                    )

                    if (
                        sellability_status
                        != "SELLABILITY_OK"
                    ):
                        block_reason = (
                            "SELLABILITY_NOT_OK"
                        )

                    elif not mathematical_plan.get(
                        "paper_eligible"
                    ):
                        block_reason = (
                            "PLAN_BLOCKED"
                        )

                    elif (
                        entry_amount_usdt <= 0
                        or token_amount <= 0
                    ):
                        block_reason = (
                            "POSITION_SIZING_BLOCKED"
                        )

                    else:
                        block_reason = None

                    # Keep collecting real price observations whenever
                    # movement evidence itself is still missing.
                    # Other plan/sizing blockers remain unchanged and
                    # watching grants no admission/trade authority.
                    watch_for_movement = (
                        _runtime_should_watch_movement(
                            block_reason,
                            plan_blockers,
                        )
                    )

                    _runtime_watch_candidate(
                        token_address,
                        market_context.get(
                            "candidate_pool"
                        ),
                        enabled=watch_for_movement,
                    )

                    if block_reason is not None:
                        combined_blockers = sorted(
                            set(
                                plan_blockers
                                + sizing_blockers
                            )
                        )

                        paper = {
                            "action": "WATCH",

                            "reason": (
                                block_reason
                            ),

                            # Compatibility field:
                            # every concrete blocker,
                            # regardless of source layer.
                            "blockers": (
                                combined_blockers
                            ),

                            "unknowns": (
                                plan_unknowns
                            ),

                            # Exact source attribution.
                            "plan_blockers": (
                                plan_blockers
                            ),

                            "plan_unknowns": (
                                plan_unknowns
                            ),

                            "sizing_blockers": (
                                sizing_blockers
                            ),

                            "sizing_reason": (
                                sizing.get(
                                    "sizing_reason"
                                )
                            ),

                            "entry_amount_usdt": (
                                entry_amount_usdt
                            ),

                            "sizing_diagnostics": {
                                "raw_plan_amount_usdt": (
                                    sizing.get(
                                        "raw_plan_amount_usdt"
                                    )
                                ),

                                "safe_quote_reserve_usd": (
                                    sizing.get(
                                        "safe_quote_reserve_usd"
                                    )
                                ),

                                "risk_log_distance": (
                                    sizing.get(
                                        "risk_log_distance"
                                    )
                                ),

                                "gap_multiplier": (
                                    sizing.get(
                                        "gap_multiplier"
                                    )
                                ),

                                "gap_samples": (
                                    sizing.get(
                                        "gap_samples"
                                    )
                                ),

                                "empirical_cost_uncertainty_fraction": (
                                    sizing.get(
                                        "empirical_cost_uncertainty_fraction"
                                    )
                                ),

                                "cost_samples": (
                                    sizing.get(
                                        "cost_samples"
                                    )
                                ),

                                "effective_edge_fraction": (
                                    sizing.get(
                                        "effective_edge_fraction"
                                    )
                                ),

                                "cost_complete": (
                                    sizing.get(
                                        "cost_complete"
                                    )
                                ),
                            },

                            "mathematical_plan": (
                                mathematical_plan
                            ),
                        }

                    else:
                        entry_wallet_id = (
                            market_context.get(
                                "wallet_id"
                            )
                        )

                        initial_sl = float(
                            (
                                mathematical_plan.get(
                                    "sl"
                                )
                                or {}
                            ).get(
                                "initial_price"
                            )
                        )

                        tp1_activation = float(
                            (
                                mathematical_plan.get(
                                    "tp1"
                                )
                                or {}
                            ).get(
                                "activation_price"
                            )
                        )

                        opening_context = {
                            "captured_at_entry": True,

                            "actor_identity": {
                                "wallet_id": (
                                    entry_wallet_id
                                ),

                                "actor_id": (
                                    entry_wallet_id
                                ),

                                "identity_source": (
                                    "TRANSACTION_FROM_ONLY"
                                    if entry_wallet_id
                                    else "UNKNOWN"
                                ),

                                "hindsight_reconstructed": (
                                    False
                                ),
                            },

                            "historical_signal": (
                                "POSITIVE"
                            ),

                            "historical_action": (
                                "ALLOW"
                            ),

                            "entry_context_version": (
                                "MATHEMATICAL_PLAN"
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
                                        ][
                                            "status"
                                        ]
                                    ),
                                )
                            ),

                            "exit_baseline": (
                                build_exit_baseline(
                                    entry_price=(
                                        price
                                    ),

                                    take_profit_price=(
                                        tp1_activation
                                    ),

                                    stop_loss_price=(
                                        initial_sl
                                    ),
                                )
                            ),

                            "mathematical_trade_plan": (
                                mathematical_plan
                            ),

                            "raw_signals": {
                                "strategy_decision": (
                                    strategy.get(
                                        "decision"
                                    )
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

                                "evidence_coverage_score": (
                                    unified_score.get(
                                        "score"
                                    )
                                ),

                                "mathematical_score": (
                                    (
                                        mathematical_plan.get(
                                            "score"
                                        )
                                        or {}
                                    ).get(
                                        "value"
                                    )
                                ),

                                "sellability_status": (
                                    analyzer_status[
                                        "sellability"
                                    ][
                                        "status"
                                    ]
                                ),

                                "pool": (
                                    market_context.get(
                                        "candidate_pool"
                                    )
                                ),

                                "quote_token": (
                                    market_context.get(
                                        "candidate_quote_token"
                                    )
                                ),

                                "runtime_context_only": (
                                    intelligence_context.get(
                                        "context_only",
                                        True,
                                    )
                                ),
                            },

                            "hindsight_reconstructed": (
                                False
                            ),

                            "trade_policy": "NORMAL",

                            "decision_authority": False,
                            "live_authority": False,
                            "wallet_authority": False,
                            "execution_authority": False,
                        }

                        opening_context_json = (
                            json.dumps(
                                opening_context,

                                sort_keys=True,

                                separators=(
                                    ",",
                                    ":",
                                ),

                                default=str,
                            )
                        )

                        mathematical_plan_json = (
                            json.dumps(
                                mathematical_plan,

                                sort_keys=True,

                                separators=(
                                    ",",
                                    ":",
                                ),

                                default=str,
                            )
                        )

                        trade_row = {
                            "token": (
                                token_address
                            ),

                            "symbol": (
                                token.get(
                                    "symbol",
                                    "?",
                                )
                            ),

                            "pool": (
                                market_context.get(
                                    "candidate_pool"
                                )
                            ),

                            "dex": (
                                market_context.get(
                                    "candidate_dex"
                                )
                            ),

                            "entry_price": (
                                price
                            ),

                            "current_price": (
                                price
                            ),

                            "highest_price": (
                                price
                            ),

                            "lowest_price": (
                                price
                            ),

                            "tp_price": (
                                tp1_activation
                            ),

                            "sl_price": (
                                initial_sl
                            ),

                            "amount_bnb": 0.0,

                            "token_amount": (
                                token_amount
                            ),

                            "initial_token_amount": (
                                token_amount
                            ),

                            "paper_account_version": (
                                "PAPER_10K_V2"
                            ),

                            "trade_policy": "NORMAL",

                            "entry_amount_usdt": (
                                entry_amount_usdt
                            ),

                            "risk_amount_usdt": (
                                sizing[
                                    "risk_amount_usdt"
                                ]
                            ),

                            "capital_before_usdt": (
                                sizing[
                                    "capital_before_usdt"
                                ]
                            ),

                            "capital_after_entry_usdt": (
                                sizing[
                                    "capital_after_entry_usdt"
                                ]
                            ),

                            "position_size_pct": (
                                sizing[
                                    "position_size_pct"
                                ]
                            ),

                            "sizing_reason": (
                                sizing[
                                    "sizing_reason"
                                ]
                            ),

                            "remaining_cost_basis_usdt": (
                                entry_amount_usdt
                            ),

                            "realized_gross_proceeds_usdt": (
                                0.0
                            ),

                            "realized_proceeds_usdt": (
                                0.0
                            ),

                            "realized_pnl_usdt": (
                                0.0
                            ),

                            "tp1_done": 0,
                            "tp2_done": 0,
                            "runner_active": 0,

                            # Legacy cost columns are deliberately
                            # not populated with invented defaults.
                            "gas_buy": None,
                            "gas_sell": None,
                            "swap_fee": None,
                            "buy_tax": None,
                            "sell_tax": None,
                            "slippage": None,
                            "mev": None,

                            "gross_pnl_usdt": (
                                0.0
                            ),

                            "net_pnl_usdt": (
                                0.0
                            ),

                            "status": "OPEN",

                            "opening_context_json": (
                                opening_context_json
                            ),

                            "mathematical_plan_json": (
                                mathematical_plan_json
                            ),

                            "math_state_json": "{}",

                            "cost_model_complete": (
                                int(
                                    bool(
                                        (
                                            mathematical_plan.get(
                                                "cost_model"
                                            )
                                            or {}
                                        ).get(
                                            "cost_complete"
                                        )
                                    )
                                )
                            ),
                        }

                        # CANONICAL_PAPER_OPENING_RISK_V1
                        opening_entry_amount = float(
                            trade_row.get(
                                "entry_amount_usdt"
                            )
                            or 0.0
                        )

                        opening_entry_price = float(
                            trade_row.get(
                                "entry_price"
                            )
                            or 0.0
                        )

                        opening_token_amount = (
                            opening_entry_amount
                            / opening_entry_price
                            if (
                                opening_entry_amount > 0
                                and opening_entry_price > 0
                            )
                            else 0.0
                        )

                        trade_row[
                            "token_amount"
                        ] = opening_token_amount

                        trade_row[
                            "remaining_cost_basis_usdt"
                        ] = opening_entry_amount

                        opening_initial_risk = (
                            initial_net_risk_usdt(
                                token_amount=(
                                    opening_token_amount
                                ),
                                entry_amount_usdt=(
                                    opening_entry_amount
                                ),
                                stop_price=(
                                    trade_row.get(
                                        "sl_price"
                                    )
                                ),
                                cost_model=(
                                    mathematical_plan.get(
                                        "cost_model"
                                    )
                                    or {}
                                ),
                            )
                        )

                        if opening_initial_risk is None:
                            opening_initial_risk = (
                                opening_entry_amount
                            )

                        sizing_tail_risk = float(
                            sizing.get(
                                "risk_amount_usdt"
                            )
                            or 0.0
                        )

                        trade_row[
                            "risk_amount_usdt"
                        ] = max(
                            float(
                                opening_initial_risk
                            ),
                            sizing_tail_risk,
                        )

                        opening_math_state = {}

                        raw_opening_state = (
                            trade_row.get(
                                "math_state_json"
                            )
                        )

                        if isinstance(
                            raw_opening_state,
                            str,
                        ) and raw_opening_state:
                            try:
                                parsed_opening_state = (
                                    json.loads(
                                        raw_opening_state
                                    )
                                )
                            except (
                                TypeError,
                                ValueError,
                                json.JSONDecodeError,
                            ):
                                parsed_opening_state = None

                            if isinstance(
                                parsed_opening_state,
                                dict,
                            ):
                                opening_math_state.update(
                                    parsed_opening_state
                                )

                        opening_math_state[
                            "initial_net_risk_usdt"
                        ] = float(
                            opening_initial_risk
                        )

                        opening_math_state[
                            "sizing_tail_risk_usdt"
                        ] = float(
                            trade_row[
                                "risk_amount_usdt"
                            ]
                        )

                        trade_row[
                            "math_state_json"
                        ] = json.dumps(
                            opening_math_state,
                            sort_keys=True,
                        )

                        bounded_insert = getattr(
                            self.paper_db,

                            "insert_if_below_open_limit",

                            None,
                        )

                        if (
                            bounded_insert
                            is not None
                        ):
                            inserted = (
                                bounded_insert(
                                    trade_row,

                                    MAX_OPEN_PAPER_POSITIONS,
                                )
                            )

                        else:
                            inserted = (
                                self.paper_db
                                .insert_if_no_open_position(
                                    trade_row
                                )
                            )

                        if not inserted:
                            if (
                                self.paper_db
                                .has_open_position(
                                    token_address
                                )
                            ):
                                reason = (
                                    "OPEN_POSITION_EXISTS"
                                )

                            elif (
                                paper_available_capital_usdt(
                                    self.paper_db.conn,
                                    PAPER_CAPITAL_USDT,
                                )
                                + 1e-9
                                < entry_amount_usdt
                            ):
                                reason = (
                                    "PAPER_CAPITAL_INSUFFICIENT"
                                )

                            else:
                                reason = (
                                    "PAPER_POSITION_CAP_REACHED"
                                )

                            paper = {
                                "action": "SKIP",
                                "reason": reason,
                            }

                        else:
                            paper = {
                                "action": (
                                    "PAPER_BUY"
                                ),

                                "token": (
                                    token_address
                                ),

                                "entry_price": (
                                    price
                                ),

                                "entry_band": {
                                    "low": (
                                        mathematical_plan[
                                            "entry"
                                        ][
                                            "band_low"
                                        ]
                                    ),

                                    "high": (
                                        mathematical_plan[
                                            "entry"
                                        ][
                                            "band_high"
                                        ]
                                    ),
                                },

                                "token_amount": (
                                    token_amount
                                ),

                                "amount_bnb": 0.0,

                                "entry_amount_usdt": (
                                    entry_amount_usdt
                                ),

                                "risk_amount_usdt": (
                                    sizing[
                                        "risk_amount_usdt"
                                    ]
                                ),

                                "position_size_pct": (
                                    sizing[
                                        "position_size_pct"
                                    ]
                                ),

                                "initial_sl": (
                                    initial_sl
                                ),

                                "tp1_activation_price": (
                                    tp1_activation
                                ),

                                "tp1_static_fraction": (
                                    None
                                ),

                                "tp2_static_fraction": (
                                    None
                                ),

                                "tp3_static_price": (
                                    None
                                ),

                                "runner_rule": (
                                    mathematical_plan[
                                        "runner"
                                    ][
                                        "rule"
                                    ]
                                ),

                                "mathematical_score": (
                                    mathematical_plan[
                                        "score"
                                    ]
                                ),

                                "cost_complete": (
                                    mathematical_plan[
                                        "cost_model"
                                    ][
                                        "cost_complete"
                                    ]
                                ),

                                "paper_account_version": (
                                    "PAPER_10K_V2"
                                ),
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
                mathematical_plan=mathematical_plan,
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

        # A scanner discovery feed may rotate a promising pool out
        # before mathematical admission has accumulated enough real
        # price movement. Refresh only explicitly watched pools using
        # the bounded multi-pool endpoint already used by the runtime.
        watch_snapshot = (
            _runtime_observation_watch_snapshot()
        )

        current_pools = {
            str(
                row.get("pool")
                or ""
            ).strip().lower()
            for row in rows
            if row.get("pool")
        }

        watch_pools = [
            pool
            for pool in watch_snapshot.values()
            if pool not in current_pools
        ]

        if watch_pools:
            pool_prices = getattr(
                self.scanner,
                "pool_prices",
                None,
            )

            update_pool_price = getattr(
                self.cache,
                "update_pool_price",
                None,
            )

            if (
                pool_prices is not None
                and update_pool_price is not None
            ):
                try:
                    watched_prices = pool_prices(
                        watch_pools
                    )

                    for (
                        watched_pool,
                        watched_price,
                    ) in watched_prices.items():
                        update_pool_price(
                            watched_pool,
                            watched_price,
                        )

                except Exception as exc:
                    logger.warning(
                        (
                            "Candidate observation price "
                            "refresh failed: %s"
                        ),
                        (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )

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

            preserve_tokens.extend(
                watch_snapshot.keys()
            )

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

    def run_cycle(
        self,
        *,
        pre_analysis_hook=None,
    ):

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

        # Candidate identities are now known but none has
        # entered analysis yet. Bind current pools and allow
        # real native BUY/SELL evidence to arrive first.
        if pre_analysis_hook is not None:
            try:
                pre_analysis_hook(
                    candidates
                )
            except Exception as exc:
                logger.warning(
                    "Pre-analysis observation binding failed: %s",
                    f"{type(exc).__name__}: {exc}",
                )

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
                    "plan_blockers": (
                        paper.get(
                            "plan_blockers"
                        )
                        or []
                    ),
                    "sizing_blockers": (
                        paper.get(
                            "sizing_blockers"
                        )
                        or []
                    ),
                    "sizing_reason": (
                        paper.get(
                            "sizing_reason"
                        )
                    ),
                    "entry_amount_usdt": (
                        paper.get(
                            "entry_amount_usdt"
                        )
                    ),
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
                        "plan_blockers=%s sizing_blockers=%s "
                        "sizing_reason=%s entry_amount_usdt=%s "
                        "hard_block=%s evidence_coverage=%s "
                        "coverage_confidence=%s sellability=%s"
                    ),
                    summary["token"],
                    summary["pool"],
                    summary["strategy"],
                    summary["unified"],
                    summary["paper"],
                    summary["reason"],
                    summary["plan_blockers"],
                    summary["sizing_blockers"],
                    summary["sizing_reason"],
                    summary["entry_amount_usdt"],
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
