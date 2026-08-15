import json
import logging
from datetime import datetime, timezone

from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice
from app.config.trading import TAKE_PROFIT, STOP_LOSS, TRAILING_STOP_FACTOR

logger = logging.getLogger(__name__)


class PaperManager:

    def __init__(self, learning_feed=None):
        self.db = PaperDatabase()
        self.price = CachePrice()
        self.learning_feed = learning_feed
        self._learning_replay_after_id = 0

    @staticmethod
    def _opening_context(pos):
        raw = (pos or {}).get(
            "opening_context_json"
        )

        if not raw:
            return None

        try:
            value = json.loads(raw)
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return None

        return (
            value
            if isinstance(value, dict)
            else None
        )

    @staticmethod
    def _expected_exit_price(
        pos,
        reason,
    ):
        if reason == "TAKE_PROFIT":
            value = (pos or {}).get(
                "tp_price"
            )
        elif reason == "STOP_LOSS":
            value = (pos or {}).get(
                "sl_price"
            )
        elif reason == "TRAILING_STOP":
            highest = (pos or {}).get(
                "highest_price"
            )

            try:
                value = (
                    float(highest)
                    * TRAILING_STOP_FACTOR
                )
            except (
                TypeError,
                ValueError,
            ):
                value = None
        else:
            value = None

        try:
            value = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        return (
            value
            if value > 0
            else None
        )

    def _observe_learning_outcome(self, pos, current, roi, reason, closed_at):
        feed = getattr(self, "learning_feed", None)
        if feed is None:
            return None
        opening_context = self._opening_context(pos)

        actor_identity = (
            opening_context.get("actor_identity")
            if isinstance(opening_context, dict)
            else None
        )

        if not isinstance(actor_identity, dict):
            actor_identity = {}

        wallet_id = actor_identity.get("wallet_id")
        actor_id = actor_identity.get("actor_id")

        return feed.observe_paper_close(
            position_id=pos["id"],
            token=pos["token"],
            observed_at=pos.get("created_at", ""),
            evaluated_at=closed_at,
            entry_price=pos["entry_price"],
            exit_price=current,
            realized_return=roi,
            close_reason=reason,
            expected_exit_price=(
                self._expected_exit_price(
                    pos,
                    reason,
                )
            ),
            opening_context=opening_context,
            wallet_id=wallet_id,
            actor_id=actor_id,
        )

    def replay_closed_outcomes(self):
        feed = getattr(self, "learning_feed", None)
        reader = getattr(self.db, "closed_positions", None)
        if feed is None or reader is None:
            return []

        results = []
        for pos in reader(after_id=self._learning_replay_after_id):
            result = self._observe_learning_outcome(
                pos,
                pos.get("exit_price"),
                pos.get("roi"),
                pos.get("close_reason"),
                pos.get("closed_at"),
            )
            results.append(result)
            self._learning_replay_after_id = max(
                self._learning_replay_after_id,
                int(pos.get("id") or 0),
            )
        return results

    def process(self):
        # Recover any DB-committed outcome whose in-memory learning step failed.
        self.replay_closed_outcomes()
        positions = self.db.open_positions()
        logger.debug("Açık Pozisyon : %d", len(positions))
        results = []

        for pos in positions:
            token = pos["token"]
            try:
                current = self.price.get_price(token)
            except Exception as e:
                logger.warning("[ERROR] token=%s error=%s", token, e)
                continue

            highest = max(pos["highest_price"], current)
            lowest = min(pos["lowest_price"], current)
            entry = pos["entry_price"]
            if entry <= 0 or pos["token_amount"] <= 0:
                continue

            current_value = pos["token_amount"] * current
            gross = current_value - pos["amount_bnb"]
            trade_value = pos["amount_bnb"]
            fees = (
                (pos["gas_buy"] or 0)
                + (pos["gas_sell"] or 0)
                + trade_value * ((pos["swap_fee"] or 0) / 100)
                + trade_value * ((pos["buy_tax"] or 0) / 100)
                + trade_value * ((pos["sell_tax"] or 0) / 100)
                + trade_value * ((pos["slippage"] or 0) / 100)
                + trade_value * ((pos["mev"] or 0) / 100)
            )
            net = gross - fees
            roi = net / pos["amount_bnb"] if pos["amount_bnb"] > 0 else 0

            self.db.update_position(
                pos["id"],
                {"current_price": current, "highest_price": highest, "lowest_price": lowest},
            )

            action = "HOLD"
            reason = ""
            trailing_price = highest * TRAILING_STOP_FACTOR
            if current <= trailing_price and highest > entry:
                action, reason = "CLOSE", "TRAILING_STOP"
            elif roi >= TAKE_PROFIT:
                action, reason = "CLOSE", "TAKE_PROFIT"
            elif roi <= STOP_LOSS:
                action, reason = "CLOSE", "STOP_LOSS"

            learning_result = None
            result_closed_at = pos.get("closed_at", "") or ""

            if action == "CLOSE":
                result_closed_at = datetime.now(timezone.utc).isoformat()
                closed = self.db.close_position(
                    pos["id"],
                    {
                        "current_price": current,
                        "exit_price": current,
                        "highest_price": highest,
                        "lowest_price": lowest,
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "roi": roi,
                        "close_reason": reason,
                        "closed_at": result_closed_at,
                    },
                )
                # Backward-compatible DB contract: only an explicit False means
                # the idempotent close lost a race. Legacy/fake DB adapters may
                # return None after a successful close.
                if closed is False:
                    action, reason = "SKIP", "ALREADY_CLOSED"
                else:
                    try:
                        outcome_position = dict(
                            pos
                        )

                        outcome_position[
                            "highest_price"
                        ] = highest

                        learning_result = (
                            self._observe_learning_outcome(
                                outcome_position,
                                current,
                                roi,
                                reason,
                                result_closed_at,
                            )
                        )
                    except Exception as exc:
                        learning_result = {
                            "state": "PENDING_REPLAY",
                            "error": type(exc).__name__,
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
