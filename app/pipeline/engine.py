import logging

from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair import analyze as pair_analyze
from app.risk.bytecode import analyze as risk_analyze
from app.risk.gate import RiskGate
from app.risk.sellability import analyze as sellability_analyze
from app.risk.traps import TrapRiskAnalyzer
from app.risk.mev import MEVExposureAnalyzer

from app.strategy.engine import StrategyEngine
from app.strategy.unified_score import UnifiedScoreEngine

from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice
from app.paper.manager import PaperManager

from app.cache.gecko_cache import GeckoCache
from app.filter.cache_filter import CacheFilter
from app.filter.ingress_gate import IngressGate
from app.pipeline.candidate_queue import CandidateAdmissionQueue
from app.pipeline.conveyor import ConveyorLabeler
from app.pipeline.work_scheduler import WorkScheduler
from app.pipeline.market_context import build_market_context
from app.scanner.adapters.source_router import normalize_source_rows

from app.config.scanner import (
    ANALYZER_WORKERS,
    MAX_PENDING_CANDIDATES,
    RECENT_ANALYSIS_COOLDOWN_SECONDS,
)

from app.config.trading import (
    DEFAULT_AMOUNT_BNB,
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
_risk_gate = RiskGate()
_trap_risk = TrapRiskAnalyzer()
_mev_risk = MEVExposureAnalyzer()


class PipelineEngine:

    def __init__(self):
        self.paper_db = PaperDatabase()
        self.price = CachePrice()
        self.cache = GeckoCache()
        self.filter = CacheFilter()
        self.ingress_gate = IngressGate()
        self.manager = PaperManager()
        self.candidate_queue = CandidateAdmissionQueue(
            max_pending=MAX_PENDING_CANDIDATES,
            cooldown_seconds=RECENT_ANALYSIS_COOLDOWN_SECONDS,
        )
        self.conveyor = ConveyorLabeler()
        self.work_scheduler = WorkScheduler(
            max_workers=ANALYZER_WORKERS
        )

    def run(
        self,
        token_address: str,
        market_context=None,
    ):

        market_context = (
            market_context or {}
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

        decision = strategy.get(
            "decision",
            "REJECT",
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

                    token_amount = DEFAULT_AMOUNT_BNB / price

                    self.paper_db.insert({

                        "token": token_address,
                        "symbol": token.get("symbol", "?"),

                        "entry_price": price,
                        "current_price": price,
                        "highest_price": price,
                        "lowest_price": price,

                        "tp_price": price * TP_PRICE_MULTIPLIER,
                        "sl_price": price * SL_PRICE_MULTIPLIER,

                        "amount_bnb": DEFAULT_AMOUNT_BNB,
                        "token_amount": token_amount,

                        "gas_buy": DEFAULT_GAS_BUY,
                        "gas_sell": DEFAULT_GAS_SELL,
                        "swap_fee": DEFAULT_SWAP_FEE,

                        "buy_tax": DEFAULT_BUY_TAX,
                        "sell_tax": DEFAULT_SELL_TAX,

                        "slippage": DEFAULT_SLIPPAGE,
                        "mev": DEFAULT_MEV_COST,

                        "status": "OPEN",
                    })

                    paper = {
                        "action": "PAPER_BUY",
                        "token": token_address,
                        "entry_price": price,
                        "token_amount": token_amount,
                        "amount_bnb": DEFAULT_AMOUNT_BNB,
                    }

        else:

            paper = {
                "action": decision,
            }

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
                "market_context": market_context,
                "analyzer_status": analyzer_status,
                "strategy": strategy,
                "paper": paper,
            },
        }

    def run_cycle(self):

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

        def process_row(row):
            token = row["token"]

            market_context = (
                build_market_context(
                    row
                )
            )

            try:
                result = self.run(
                    token,
                    market_context=(
                        market_context
                    ),
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

        try:
            self.manager.process()
        except Exception:
            logger.exception(
                "Paper manager exception"
            )

