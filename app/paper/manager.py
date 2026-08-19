import json
import logging
from datetime import datetime, timezone

from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice
from app.risk.hybrid_exit_controller import evaluate_hybrid_exit
from app.risk.hybrid_exit_runtime_adapter import build_hybrid_exit_runtime_input

logger = logging.getLogger(__name__)


class PaperManager:

    def __init__(self, learning_feed=None, hybrid_exit_evidence=None):
        self.db = PaperDatabase()
        self.price = CachePrice()
        self.learning_feed = learning_feed
        self.hybrid_exit_evidence = hybrid_exit_evidence
        self._learning_replay_after_id = 0

    @staticmethod
    def _opening_context(pos):
        raw = (pos or {}).get("opening_context_json")
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _expected_exit_price(pos, reason):
        if reason in {"DYNAMIC_PROTECTION_FLOOR", "DYNAMIC_PROFIT_PROTECTION", "SEVERE_MARKET_DETERIORATION", "PERSISTED_STOP_LOSS"}:
            value = (pos or {}).get("sl_price")
        else:
            value = None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @staticmethod
    def _is_10k_account(pos):
        return (pos or {}).get("paper_account_version") == "PAPER_10K_V2"

    @staticmethod
    def _calculate_accounting(pos, current):
        token_amount = float(pos.get("token_amount") or 0.0)
        if token_amount <= 0:
            return None
        if PaperManager._is_10k_account(pos):
            entry_amount = float(pos.get("entry_amount_usdt") or 0.0)
            if entry_amount <= 0:
                return None
            current_value = token_amount * current
            gross = current_value - entry_amount
            trade_value = entry_amount
            account = "PAPER_10K_V2"
        else:
            entry_amount = float(pos.get("amount_bnb") or 0.0)
            if entry_amount <= 0:
                return None
            current_value = token_amount * current
            gross = current_value - entry_amount
            trade_value = entry_amount
            account = "LEGACY"
        fees = (float(pos.get("gas_buy") or 0) + float(pos.get("gas_sell") or 0) + trade_value * float(pos.get("swap_fee") or 0) / 100 + trade_value * float(pos.get("buy_tax") or 0) / 100 + trade_value * float(pos.get("sell_tax") or 0) / 100 + trade_value * float(pos.get("slippage") or 0) / 100 + trade_value * float(pos.get("mev") or 0) / 100)
        net = gross - fees
        roi = net / entry_amount
        return {"gross": gross, "net": net, "roi": roi, "gross_pnl_usdt": gross if account == "PAPER_10K_V2" else None, "net_pnl_usdt": net if account == "PAPER_10K_V2" else None, "account": account}

    def _observe_learning_outcome(self, pos, current, roi, reason, closed_at):
        feed = getattr(self, "learning_feed", None)
        if feed is None:
            return None
        opening_context = self._opening_context(pos)
        actor_identity = opening_context.get("actor_identity") if isinstance(opening_context, dict) else None
        if not isinstance(actor_identity, dict):
            actor_identity = {}
        return feed.observe_paper_close(position_id=pos["id"], token=pos["token"], observed_at=pos.get("created_at", ""), evaluated_at=closed_at, entry_price=pos["entry_price"], exit_price=current, realized_return=roi, close_reason=reason, expected_exit_price=self._expected_exit_price(pos, reason), opening_context=opening_context, wallet_id=actor_identity.get("wallet_id"), actor_id=actor_identity.get("actor_id"))

    def replay_closed_outcomes(self):
        feed = getattr(self, "learning_feed", None)
        reader = getattr(self.db, "closed_positions", None)
        if feed is None or reader is None:
            return []
        results = []
        for pos in reader(after_id=self._learning_replay_after_id):
            results.append(self._observe_learning_outcome(pos, pos.get("exit_price"), pos.get("roi"), pos.get("close_reason"), pos.get("closed_at")))
            self._learning_replay_after_id = max(self._learning_replay_after_id, int(pos.get("id") or 0))
        return results

    def _hybrid_runtime_evidence(self, pos):
        source = getattr(self, "hybrid_exit_evidence", None)
        if source is None:
            return None
        try:
            if callable(source):
                value = source(pos)
            elif isinstance(source, dict):
                token = (pos or {}).get("token")
                value = source.get(token) if token in source else source
            else:
                return None
        except Exception as exc:
            logger.warning("hybrid exit evidence unavailable position_id=%s error=%s", (pos or {}).get("id"), type(exc).__name__)
            return None
        return dict(value) if isinstance(value, dict) else None

    def _evaluate_hybrid_paper_exit(self, *, pos, current, highest):
        # Optional intelligence enriches the controller; it is never required
        # for deterministic adaptive protection to remain active.
        evidence = self._hybrid_runtime_evidence(pos) or {}
        signal_bundle = evidence.get("signal_bundle")
        if not isinstance(signal_bundle, dict):
            signal_bundle = {}
        runtime_input = build_hybrid_exit_runtime_input(
            position_state={"entry_price": pos.get("entry_price"), "current_price": current, "highest_price": highest, "sl_price": pos.get("sl_price")},
            signal_bundle=signal_bundle, trend_health=evidence.get("trend_health"), exit_pressure=evidence.get("exit_pressure"), hard_block=bool(evidence.get("hard_block", False)), sellability=evidence.get("sellability"),
        )
        controller_keys = ("entry_price", "current_price", "highest_price", "static_sl_price", "hard_block", "sellability", "liquidity_health", "flow_momentum", "flow_acceleration", "trend_health", "exit_pressure", "price_impact_health", "atr_pct")
        decision = evaluate_hybrid_exit(**{key: runtime_input.get(key) for key in controller_keys})
        return {"decision": decision, "runtime_input": runtime_input}

    def process(self):
        self.replay_closed_outcomes()
        positions = self.db.open_positions()
        logger.debug("Açık Pozisyon : %d", len(positions))
        results = []
        for pos in positions:
            token = pos["token"]
            try:
                current = self.price.get_price(token)
            except Exception as exc:
                logger.warning("[ERROR] token=%s error=%s", token, exc)
                continue
            highest = max(float(pos["highest_price"]), current)
            lowest = min(float(pos["lowest_price"]), current)
            entry = float(pos["entry_price"])
            if entry <= 0 or float(pos["token_amount"]) <= 0:
                continue
            accounting = self._calculate_accounting(pos, current)
            if accounting is None:
                logger.warning("paper accounting unavailable position_id=%s account=%s", pos.get("id"), pos.get("paper_account_version"))
                continue
            gross, net, roi = accounting["gross"], accounting["net"], accounting["roi"]
            update = {"current_price": current, "highest_price": highest, "lowest_price": lowest, "gross_pnl": gross, "net_pnl": net, "roi": roi}
            if accounting["account"] == "PAPER_10K_V2":
                update["gross_pnl_usdt"] = accounting["gross_pnl_usdt"]
                update["net_pnl_usdt"] = accounting["net_pnl_usdt"]

            persisted_floor = float(pos.get("sl_price") or 0.0)
            action = "HOLD"
            reason = "NO_EXIT_CONDITION"
            hybrid_decision = None

            if persisted_floor > 0 and current <= persisted_floor:
                action = "CLOSE"
                reason = "PERSISTED_STOP_LOSS"
            else:
                hybrid_result = self._evaluate_hybrid_paper_exit(pos=pos, current=current, highest=highest)
                hybrid_decision = hybrid_result["decision"]
                reason = hybrid_decision.reason
                if hybrid_decision.protection_price is not None:
                    raised_floor = max(persisted_floor, float(hybrid_decision.protection_price))
                    if raised_floor > 0:
                        update["sl_price"] = raised_floor
                        pos["sl_price"] = raised_floor
                if hybrid_decision.exit_now:
                    action = "CLOSE"

            self.db.update_position(pos["id"], update)
            learning_result = None
            result_closed_at = pos.get("closed_at", "") or ""
            if action == "CLOSE":
                result_closed_at = datetime.now(timezone.utc).isoformat()
                close_data = {"current_price": current, "exit_price": current, "highest_price": highest, "lowest_price": lowest, "gross_pnl": gross, "net_pnl": net, "roi": roi, "close_reason": reason, "closed_at": result_closed_at}
                if accounting["account"] == "PAPER_10K_V2":
                    close_data["gross_pnl_usdt"] = accounting["gross_pnl_usdt"]
                    close_data["net_pnl_usdt"] = accounting["net_pnl_usdt"]
                closed = self.db.close_position(pos["id"], close_data)
                if closed is False:
                    action, reason = "SKIP", "ALREADY_CLOSED"
                else:
                    try:
                        outcome_position = dict(pos)
                        outcome_position["highest_price"] = highest
                        learning_result = self._observe_learning_outcome(outcome_position, current, roi, reason, result_closed_at)
                    except Exception as exc:
                        learning_result = {"state": "PENDING_REPLAY", "error": type(exc).__name__, "proposal_only": True, "automatic_apply_allowed": False}

            status = "CLOSED" if action == "CLOSE" else "OPEN"
            hybrid_payload = {"bound": hybrid_decision is not None, "decision_authority": False, "live_authority": False, "wallet_authority": False, "execution_authority": False}
            if hybrid_decision is not None:
                hybrid_payload.update({"action": hybrid_decision.action, "reason": hybrid_decision.reason, "exit_now": hybrid_decision.exit_now, "protect_profit": hybrid_decision.protect_profit, "runner_active": hybrid_decision.runner_active, "protection_price": hybrid_decision.protection_price, "profit_lock_price": hybrid_decision.profit_lock_price, "health_score": hybrid_decision.health_score})
            results.append({"success": True, "source": "paper", "data": {"action": action, "token": token, "entry_price": entry, "current_price": current, "roi": roi, "status": status, "opened_at": pos.get("created_at", ""), "closed_at": result_closed_at, "reason": reason, "account": accounting["account"], "gross_pnl_usdt": accounting["gross_pnl_usdt"], "net_pnl_usdt": accounting["net_pnl_usdt"], "learning": learning_result, "hybrid_exit": hybrid_payload}})
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    PaperManager().process()
