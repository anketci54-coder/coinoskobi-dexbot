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

    def run(self, token_address: str):

        token = token_analyze(token_address).get("data", {})

        pair = pair_analyze(token_address).get("data", {})

        risk = risk_analyze(token_address).get("data", {})

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
                "strategy": strategy,
                "paper": paper,
            },
        }

    def run_cycle(self):

        rows = self.cache.all()
        candidates = self.filter.filter(rows)

        logger.info(
            "Cache=%s Candidates=%s",
            len(rows),
            len(candidates),
        )

        for row in candidates:

            token = row["token"]

            if "_" in token:
                token = token.split("_", 1)[1]

            result = self.run(token)

            if not result.get("success"):
                logger.warning("Pipeline failed: %s", token)

        self.manager.process()
