import logging
from datetime import datetime, timezone

from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice
from app.config.trading import TAKE_PROFIT, STOP_LOSS, TRAILING_STOP_FACTOR

logger = logging.getLogger(__name__)


class PaperManager:

    def __init__(
        self,
        learning_feed=None,
    ):

        self.db = PaperDatabase()
        self.price = CachePrice()
        self.learning_feed = learning_feed

    def process(self):

        positions = self.db.open_positions()

        logger.debug("Açık Pozisyon : %d", len(positions))

        results = []

        for pos in positions:

            token = pos["token"]

            try:
                current = self.price.get_price(token)
                logger.debug("[PRICE] token=%s current=%s", token, current)
            except Exception as e:
                logger.warning("[ERROR] token=%s error=%s", token, e)
                continue

            highest = max(pos["highest_price"], current)
            lowest  = min(pos["lowest_price"],  current)

            entry = pos["entry_price"]

            logger.debug("[ENTRY] token=%s entry=%s", token, entry)

            if entry <= 0:
                logger.debug("[SKIP] token=%s entry_price<=0", token)
                continue

            token_amount = pos["token_amount"]

            if token_amount <= 0:
                continue

            current_value = token_amount * current

            gross = current_value - pos["amount_bnb"]

            trade_value = pos["amount_bnb"]

            swap_fee_cost  = trade_value * ((pos["swap_fee"]  or 0) / 100)
            buy_tax_cost   = trade_value * ((pos["buy_tax"]   or 0) / 100)
            sell_tax_cost  = trade_value * ((pos["sell_tax"]  or 0) / 100)
            slippage_cost  = trade_value * ((pos["slippage"]  or 0) / 100)
            mev_cost       = trade_value * ((pos["mev"]       or 0) / 100)

            fees = (
                (pos["gas_buy"]  or 0)
                + (pos["gas_sell"] or 0)
                + swap_fee_cost
                + buy_tax_cost
                + sell_tax_cost
                + slippage_cost
                + mev_cost
            )

            net = gross - fees

            roi = (
                net / pos["amount_bnb"]
                if pos["amount_bnb"] > 0
                else 0
            )

            self.db.update_position(
                pos["id"],
                {
                    "current_price": current,
                    "highest_price": highest,
                    "lowest_price": lowest,
                },
            )

            logger.debug(
                "%s... ROI=%.2f%% Current=%.10f",
                token[:10], roi * 100, current
            )

            action = "HOLD"
            reason = ""

            trailing_price = highest * TRAILING_STOP_FACTOR

            if current <= trailing_price and highest > entry:

                self.db.close_position(
                    pos["id"],
                    {
                        "current_price": current,
                        "exit_price": current,
                        "highest_price": highest,
                        "lowest_price": lowest,
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "roi": roi,
                        "close_reason": "TRAILING_STOP",
                        "closed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

                action = "CLOSE"
                reason = "TRAILING_STOP"
                logger.debug(">>> TRAILING STOP token=%s", token)

            elif roi >= TAKE_PROFIT:

                self.db.close_position(
                    pos["id"],
                    {
                        "current_price": current,
                        "exit_price": current,
                        "highest_price": highest,
                        "lowest_price": lowest,
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "roi": roi,
                        "close_reason": "TAKE_PROFIT",
                        "closed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

                action = "CLOSE"
                reason = "TAKE_PROFIT"
                logger.debug(">>> TAKE PROFIT token=%s", token)

            elif roi <= STOP_LOSS:

                self.db.close_position(
                    pos["id"],
                    {
                        "current_price": current,
                        "exit_price": current,
                        "highest_price": highest,
                        "lowest_price": lowest,
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "roi": roi,
                        "close_reason": "STOP_LOSS",
                        "closed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

                action = "CLOSE"
                reason = "STOP_LOSS"
                logger.debug(">>> STOP LOSS token=%s", token)

            status = "CLOSED" if action == "CLOSE" else "OPEN"

            learning_result = None
            result_closed_at = (
                pos.get("closed_at", "")
                or ""
            )

            learning_feed = getattr(
                self,
                "learning_feed",
                None,
            )

            if (
                action == "CLOSE"
                and learning_feed is not None
            ):
                result_closed_at = (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                )

                learning_result = (
                    learning_feed.observe_paper_close(
                        position_id=pos["id"],
                        token=token,
                        observed_at=pos.get(
                            "created_at",
                            "",
                        ),
                        evaluated_at=(
                            result_closed_at
                        ),
                        entry_price=entry,
                        exit_price=current,
                        realized_return=roi,
                        close_reason=reason,
                        opening_context=None,
                    )
                )

            results.append({
                "success": True,
                "source":  "paper",
                "data": {
                    "action":        action,
                    "token":         token,
                    "entry_price":   entry,
                    "current_price": current,
                    "roi":           roi,
                    "status":        status,
                    "opened_at":     pos.get("created_at", ""),
                    "closed_at":     result_closed_at,
                    "reason":        reason,
                    "learning":      learning_result,
                },
            })

        return results


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    PaperManager().process()
