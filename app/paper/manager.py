import logging

from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice

logger = logging.getLogger(__name__)


class PaperManager:

    TAKE_PROFIT = 0.20
    STOP_LOSS = -0.10

    def __init__(self):

        self.db = PaperDatabase()
        self.price = CachePrice()

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
            lowest = min(pos["lowest_price"], current)

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

            swap_fee_cost = trade_value * ((pos["swap_fee"] or 0) / 100)
            buy_tax_cost = trade_value * ((pos["buy_tax"] or 0) / 100)
            sell_tax_cost = trade_value * ((pos["sell_tax"] or 0) / 100)
            slippage_cost = trade_value * ((pos["slippage"] or 0) / 100)
            mev_cost = trade_value * ((pos["mev"] or 0) / 100)

            fees = (
                (pos["gas_buy"] or 0)
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

                current_price=current,
                highest_price=highest,
                lowest_price=lowest

            )

            logger.debug(
                "%s... ROI=%.2f%% Current=%.10f",
                token[:10], roi * 100, current
            )

            action = "HOLD"
            reason = ""

            trailing_price = highest * 0.90

            if current <= trailing_price and highest > entry:

                self.db.close_position(

                    pos["id"],
                    current,
                    gross,
                    net,
                    roi,
                    "TRAILING_STOP"

                )

                action = "CLOSE"
                reason = "TRAILING_STOP"
                logger.debug(">>> TRAILING STOP token=%s", token)

            elif roi >= self.TAKE_PROFIT:

                self.db.close_position(

                    pos["id"],
                    current,
                    gross,
                    net,
                    roi,
                    "TAKE_PROFIT"

                )

                action = "CLOSE"
                reason = "TAKE_PROFIT"
                logger.debug(">>> TAKE PROFIT token=%s", token)

            elif roi <= self.STOP_LOSS:

                self.db.close_position(

                    pos["id"],
                    current,
                    gross,
                    net,
                    roi,
                    "STOP_LOSS"

                )

                action = "CLOSE"
                reason = "STOP_LOSS"
                logger.debug(">>> STOP LOSS token=%s", token)

            status = "CLOSED" if action == "CLOSE" else "OPEN"

            results.append({
                "success": True,
                "source": "paper",
                "data": {
                    "action": action,
                    "token": token,
                    "entry_price": entry,
                    "current_price": current,
                    "roi": roi,
                    "status": status,
                    "opened_at": pos.get("created_at", ""),
                    "closed_at": pos.get("closed_at", "") or "",
                    "reason": reason,
                },
            })

        return results


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    PaperManager().process()
