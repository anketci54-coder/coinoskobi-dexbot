import logging

from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair  import analyze as pair_analyze
from app.risk.bytecode  import analyze as risk_analyze
from app.strategy.engine import StrategyEngine
from app.paper.database  import PaperDatabase
from app.paper.cache_price import CachePrice
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
        self.price    = CachePrice()

    def run(self, token_address: str) -> dict:
        """
        Execute the full analysis pipeline for a single token address.

        Returns the standardized pipeline envelope:
        {
            "success": bool,
            "source": "pipeline",
            "data": {
                "token": {},
                "pair": {},
                "risk": {},
                "strategy": {},
                "paper": {}
            }
        }
        """

        # --- Analyzer ---

        token_result = token_analyze(token_address)
        pair_result  = pair_analyze(token_address)
        risk_result  = risk_analyze(token_address)

        token = token_result.get("data", {})
        pair  = pair_result.get("data",  {})
        risk  = risk_result.get("data",  {})

        # --- Strategy ---

        strategy_result = _strategy.evaluate(token, pair, risk)
        strategy_data   = strategy_result.get("data", {})

        decision = strategy_data.get("decision", "REJECT")

        # --- Paper ---

        paper_data = {}

        if decision == "PAPER_BUY":

            if self.paper_db.has_open_position(token_address):

                logger.debug("[PIPELINE] open position exists: %s", token_address)
                paper_data = {"action": "SKIP", "reason": "OPEN_POSITION_EXISTS"}

            else:

                try:
                    price = self.price.get_price(token_address)
                except Exception:
                    price = 0.0

                if price <= 0:

                    logger.debug("[PIPELINE] price unavailable: %s", token_address)
                    paper_data = {"action": "SKIP", "reason": "PRICE_UNAVAILABLE"}

                else:

                    token_amount = DEFAULT_AMOUNT_BNB / price

                    self.paper_db.insert({

                        "token":         token_address,
                        "symbol":        token.get("symbol", "?"),

                        "entry_price":   price,
                        "current_price": price,
                        "highest_price": price,
                        "lowest_price":  price,

                        "tp_price":      price * TP_PRICE_MULTIPLIER,
                        "sl_price":      price * SL_PRICE_MULTIPLIER,

                        "amount_bnb":    DEFAULT_AMOUNT_BNB,
                        "token_amount":  token_amount,

                        "gas_buy":       DEFAULT_GAS_BUY,
                        "gas_sell":      DEFAULT_GAS_SELL,

                        "swap_fee":      DEFAULT_SWAP_FEE,
                        "buy_tax":       DEFAULT_BUY_TAX,
                        "sell_tax":      DEFAULT_SELL_TAX,
                        "slippage":      DEFAULT_SLIPPAGE,
                        "mev":           DEFAULT_MEV_COST,

                        "status": "OPEN"

                    })

                    logger.debug("[PIPELINE] paper buy inserted: %s", token_address)

                    paper_data = {
                        "action":       "PAPER_BUY",
                        "token":        token_address,
                        "entry_price":  price,
                        "token_amount": token_amount,
                        "amount_bnb":   DEFAULT_AMOUNT_BNB,
                    }

        else:

            paper_data = {"action": decision}

        return {
            "success": True,
            "source":  "pipeline",
            "data": {
                "token":    token,
                "pair":     pair,
                "risk":     risk,
                "strategy": strategy_data,
                "paper":    paper_data,
            },
        }
