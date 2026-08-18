STATE_OPEN = "OPEN"
STATE_TP1_DONE = "TP1_DONE"
STATE_TP2_DONE = "TP2_DONE"
STATE_TP3_DONE = "TP3_DONE"
STATE_RUNNER_ACTIVE = "RUNNER_ACTIVE"


class PositionLifecycleEngine:
    """Pure-local dynamic position lifecycle contract.

    The system derives SL, TP1/2/3 and exit fractions from the entry-time
    score/confidence/sellability evidence. The result is deterministic and
    advisory/mechanical only: no DB, execution, wallet or live authority.
    """

    @staticmethod
    def build_plan(*, entry_price, score, confidence, sellability, hard_block=False):
        entry_price = float(entry_price)
        score = max(0.0, min(100.0, float(score or 0.0)))
        confidence = max(0.0, min(100.0, float(confidence or 0.0)))
        sellability = str(sellability or "SELLABILITY_UNKNOWN").upper()

        if entry_price <= 0:
            raise ValueError("entry_price must be positive")

        blocked = bool(hard_block) or sellability in {
            "SELLABILITY_FAIL", "SELLABILITY_BLOCK", "BLOCKED", "FAIL"
        }
        if blocked:
            return {
                "eligible": False,
                "reason": "HARD_BLOCK_OR_SELLABILITY_FAIL",
                "entry_price": entry_price,
                "decision_authority": False,
                "execution_authority": False,
            }

        quality = (0.65 * score + 0.35 * confidence) / 100.0
        quality = max(0.0, min(1.0, quality))
        unknown = sellability in {"SELLABILITY_UNKNOWN", "UNKNOWN", ""}
        if unknown:
            quality *= 0.85

        # Better evidence earns a little more breathing room and wider targets.
        sl_roi = -(0.07 + 0.05 * quality)          # -7% .. -12%
        tp1_roi = 0.10 + 0.10 * quality           # +10% .. +20%
        tp2_roi = 0.25 + 0.25 * quality           # +25% .. +50%
        tp3_roi = 0.55 + 0.45 * quality           # +55% .. +100%

        # Stronger setups retain more runner; weaker/unknown setups realize
        # profit earlier. Fractions always sum to 1.0.
        runner = 0.15 + 0.15 * quality
        if unknown:
            runner = max(0.10, runner - 0.05)
        tp1_fraction = 0.40 - 0.15 * quality
        tp2_fraction = 0.30 - 0.05 * quality
        tp3_fraction = 1.0 - runner - tp1_fraction - tp2_fraction

        fractions = [tp1_fraction, tp2_fraction, tp3_fraction, runner]
        fractions = [round(x, 6) for x in fractions]
        fractions[2] = round(1.0 - fractions[0] - fractions[1] - fractions[3], 6)

        return {
            "eligible": True,
            "reason": "DYNAMIC_ENTRY_EVIDENCE_PLAN",
            "entry_price": entry_price,
            "quality": round(quality, 6),
            "sl_roi": round(sl_roi, 6),
            "tp1_roi": round(tp1_roi, 6),
            "tp2_roi": round(tp2_roi, 6),
            "tp3_roi": round(tp3_roi, 6),
            "sl_price": entry_price * (1.0 + sl_roi),
            "tp1_price": entry_price * (1.0 + tp1_roi),
            "tp2_price": entry_price * (1.0 + tp2_roi),
            "tp3_price": entry_price * (1.0 + tp3_roi),
            "tp1_close_fraction": fractions[0],
            "tp2_close_fraction": fractions[1],
            "tp3_close_fraction": fractions[2],
            "runner_fraction": fractions[3],
            "sellability": sellability,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def evaluate(self, *, roi, plan=None, tp1_done=False, tp2_done=False, tp3_done=False):
        plan = plan or {}
        if not plan.get("eligible", True):
            return self._result(STATE_OPEN, "HOLD", 0.0, "PLAN_NOT_ELIGIBLE")
        if roi is None:
            return self._result(STATE_OPEN, "HOLD", 0.0, "ROI_UNKNOWN")

        roi = float(roi)
        tp1 = float(plan.get("tp1_roi", 0.20))
        tp2 = float(plan.get("tp2_roi", 0.50))
        tp3 = float(plan.get("tp3_roi", 1.00))
        f1 = float(plan.get("tp1_close_fraction", 0.20))
        f2 = float(plan.get("tp2_close_fraction", 0.25))
        f3 = float(plan.get("tp3_close_fraction", 0.25))

        if not tp1_done and roi >= tp1:
            return self._result(STATE_TP1_DONE, "PARTIAL_CLOSE", f1, "TP1_REACHED")
        if tp1_done and not tp2_done and roi >= tp2:
            return self._result(STATE_TP2_DONE, "PARTIAL_CLOSE", f2, "TP2_REACHED")
        if tp1_done and tp2_done and not tp3_done and roi >= tp3:
            return self._result(STATE_TP3_DONE, "PARTIAL_CLOSE", f3, "TP3_REACHED")
        if tp1_done and tp2_done and tp3_done:
            return self._result(STATE_RUNNER_ACTIVE, "HOLD_RUNNER", 0.0, "RUNNER_ACTIVE")

        state = STATE_TP3_DONE if tp3_done else STATE_TP2_DONE if tp2_done else STATE_TP1_DONE if tp1_done else STATE_OPEN
        return self._result(state, "HOLD", 0.0, "NO_TARGET_REACHED")

    @staticmethod
    def _result(state, action, close_fraction, reason):
        return {
            "state": state,
            "action": action,
            "close_fraction": close_fraction,
            "reason": reason,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
