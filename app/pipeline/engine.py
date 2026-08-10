import logging

from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair import analyze as pair_analyze
from app.risk.bytecode import analyze as risk_analyze

from app.strategy.engine import StrategyEngine

from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice
from app.paper.manager import PaperManager

from app.cache.gecko_cache import GeckoCache
from app.filter.cache_filter import CacheFilter
from app.pipeline.candidate_queue import CandidateAdmissionQueue

from app.config.scanner import (
    MAX_PENDING_CANDIDATES,
    MAX_RPC_CANDIDATES,
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


class PipelineEngine:

    def __init__(self):
        self.paper_db = PaperDatabase()
        self.price = CachePrice()
        self.cache = GeckoCache()
        self.filter = CacheFilter()
        self.manager = PaperManager()
        self.candidate_queue = CandidateAdmissionQueue(
            max_pending=MAX_PENDING_CANDIDATES,
            cooldown_seconds=RECENT_ANALYSIS_COOLDOWN_SECONDS,
        )

    def run(self, token_address: str):

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

        strategy = _strategy.evaluate(
            token,
            pair,
            risk,
        ).get("data", {})

        decision = strategy.get("decision", "REJECT")

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
                "analyzer_status": analyzer_status,
                "strategy": strategy,
                "paper": paper,
            },
        }

    def run_cycle(self):

        rows = self.cache.all()

        if hasattr(self.filter, "filter_all"):
            candidates = self.filter.filter_all(rows)
        else:
            candidates = self.filter.filter(rows)

        if not hasattr(self, "candidate_queue"):
            self.candidate_queue = CandidateAdmissionQueue(
                max_pending=MAX_PENDING_CANDIDATES,
                cooldown_seconds=RECENT_ANALYSIS_COOLDOWN_SECONDS,
            )

        self.candidate_queue.enqueue_many(candidates)

        admitted = self.candidate_queue.pop_many(
            MAX_RPC_CANDIDATES
        )

        queue_stats = self.candidate_queue.stats()

        logger.info(
            (
                "Cache=%s Candidates=%s "
                "Admitted=%s Pending=%s "
                "Duplicates=%s CooldownSkipped=%s"
            ),
            len(rows),
            len(candidates),
            len(admitted),
            queue_stats["pending"],
            queue_stats["duplicates_collapsed"],
            queue_stats["cooldown_skipped"],
        )

        for row in admitted:

            token = row["token"]

            try:
                result = self.run(token)

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

            finally:
                self.candidate_queue.mark_analyzed(
                    token
                )

        try:
            self.manager.process()
        except Exception:
            logger.exception(
                "Paper manager exception"
            )

