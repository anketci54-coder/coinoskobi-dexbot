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
        self._learning_replay_after_id = 0

    def _observe_learning_outcome(
        self,
        pos,
        *,
        current,
        roi,
        reason,
        closed_at,
    ):
        learning_feed = getattr(
            self,
            "learning_feed",
            None,
        )

        if learning_feed is None:
            return None

        return learning_feed.observe_paper_close(
            position_id=pos["id"],
            token=pos["token"],
            observed_at=pos.get("created_at", ""),
            evaluated_at=closed_at,
            entry_price=pos["entry_price"],
            exit_price=current,
            realized_return=roi,
            close_reason=reason,
            opening_context=None,
        )

    def replay_closed_outcomes(self):
        """Recover committed paper outcomes after failure/restart.

        CLOSED paper rows are durable. Runtime learning memory is
        bounded and may be rebuilt by replay. The learning adapter is
        idempotent by paper position id, so replay cannot double-count
        an already observed outcome.
        """
        learning_feed = getattr(
            self,
            "learning_feed",
            None,
        )
        closed_reader = getattr(
            self.db,
            "closed_positions",
            None,
        )

        if learning_feed is None or closed_reader is None:
            return []

        after_id = getattr(
            self,
            "_learning_replay_after_id",
            0,
        )
        results = []

        for pos in closed_reader(after_id=after_id):
            result = self._observe_learning_outcome(
                pos,
                current=pos.get("exit_price"),
                roi=pos.get("roi"),
                reason=pos.get("close_reason"),
                closed_at=pos.get("closed_at"),
            )
            results.append(result)
            self._learning_replay_after_id = max(
                int(pos.get("id") or 0),
                int(getattr(
                    self,
                    "_learning_replay_after_id",
                    0,
                )),
            )

        return results

    def process(self):
        # Repair the DB-close -> learning gap before new work.
        self.replay_closed_outcomes()

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
                {
                    "current_price": current,
                    "highest_price": highest,
                    "lowest_price": lowest,
                },
            )

            action = "HOLD"
            reason = ""
            trailing_price = highest * TRAILING_STOP_FACTOR

            if current <= trailing_price and highest > entry:
                action = "CLOSE"
                reason = "TRAILING_STOP"
            elif roi >= TAKE_PROFIT:
                action = "CLOSE"
                reason = "TAKE_PROFIT"
            elif roi <= STOP_LOSS:
                action = "CLOSE"
                reason = "STOP_LOSS"

            learning_result = None
            result_closed_at = pos.get("closed_at", "") or ""

            if action == "CLOSE":
                result_closed_at = datetime.now(
                    timezone.utc
                ).isoformat()
                close_values = {
                    "current_price": current,
                    "exit_price": current,
                    "highest_price": highest,
                    "lowest_price": lowest,
                    "gross_pnl": gross,
                    "net_pnl": net,
                    "roi": roi,
                    "close_reason": reason,
                    "closed_at": result_closed_at,
                }

                closed = self.db.close_position(
                    pos["id"],
                    close_values,
                )

                if closed is False:
                    # Another process won the idempotent close race.
                    action = "SKIP"
                    reason = "ALREADY_CLOSED"
                else:
                    try:
                        learning_result = self._observe_learning_outcome(
                            pos,
                            current=current,
                            roi=roi,
                            reason=reason,
                            closed_at=result_closed_at,
                        )
                    except Exception as exc:
                        # The DB close remains durable and replayable.
                        learning_result = {
                            "state": "PENDING_REPLAY",
                            "error": f"{type(exc).__name__}: {exc}",
                            "proposal_only": True,
                            "automatic_apply_allowed": False,
                        }

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
                    "closed_at": result_closed_at,
                    "reason": reason,
                    "learning": learning_result,
                },
            })

        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    PaperManager().process()
