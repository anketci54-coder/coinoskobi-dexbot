import math


STATE_OPEN = "OPEN"
STATE_TP1_DONE = "TP1_DONE"
STATE_TP2_DONE = "TP2_DONE"
STATE_TP3_DONE = "TP3_DONE"
STATE_RUNNER_ACTIVE = "RUNNER_ACTIVE"


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def _fraction(value):
    value = _number(value)

    if (
        value is None
        or value <= 0
        or value > 1
    ):
        return None

    return value


class PositionLifecycleEngine:
    """
    Compatibility lifecycle contract.

    It consumes a canonical mathematical plan.
    It does not invent SL/TP/fractions.
    """

    @staticmethod
    def build_plan(
        *,
        entry_price,
        score=None,
        confidence=None,
        sellability=None,
        hard_block=False,
        mathematical_plan=None,
    ):
        entry = _number(entry_price)

        if entry is None or entry <= 0:
            raise ValueError(
                "entry_price must be positive"
            )

        status = str(
            sellability
            or "SELLABILITY_UNKNOWN"
        ).upper()

        if (
            hard_block
            or status
            in {
                "SELLABILITY_FAIL",
                "SELLABILITY_BLOCK",
                "BLOCKED",
                "FAIL",
            }
        ):
            return {
                "eligible": False,
                "reason": (
                    "HARD_BLOCK_OR_SELLABILITY_FAIL"
                ),
                "entry_price": entry,
                "decision_authority": False,
                "execution_authority": False,
            }

        if status != "SELLABILITY_OK":
            return {
                "eligible": False,
                "reason": (
                    "SELLABILITY_NOT_CONFIRMED"
                ),
                "entry_price": entry,
                "decision_authority": False,
                "execution_authority": False,
            }

        if not isinstance(
            mathematical_plan,
            dict,
        ):
            return {
                "eligible": False,
                "reason": (
                    "MATHEMATICAL_PLAN_REQUIRED"
                ),
                "entry_price": entry,
                "decision_authority": False,
                "execution_authority": False,
            }

        if (
            mathematical_plan.get(
                "paper_eligible"
            )
            is not True
        ):
            return {
                "eligible": False,
                "reason": (
                    "MATHEMATICAL_PLAN_NOT_ELIGIBLE"
                ),
                "entry_price": entry,
                "decision_authority": False,
                "execution_authority": False,
            }

        return {
            "eligible": True,
            "reason": (
                "CANONICAL_MATHEMATICAL_PLAN"
            ),
            "entry_price": entry,
            "mathematical_plan": (
                mathematical_plan
            ),
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def evaluate(
        self,
        *,
        roi,
        plan=None,
        tp1_done=False,
        tp2_done=False,
        tp3_done=False,
    ):
        plan = plan or {}

        if plan.get("eligible") is False:
            return self._result(
                STATE_OPEN,
                "HOLD",
                0.0,
                "PLAN_NOT_ELIGIBLE",
            )

        roi_value = _number(roi)

        if roi_value is None:
            return self._result(
                STATE_OPEN,
                "HOLD",
                0.0,
                "ROI_UNKNOWN",
            )

        tp1 = _number(
            plan.get("tp1_roi")
        )
        tp2 = _number(
            plan.get("tp2_roi")
        )
        f1 = _fraction(
            plan.get(
                "tp1_close_fraction"
            )
        )
        f2 = _fraction(
            plan.get(
                "tp2_close_fraction"
            )
        )

        if None in {
            tp1,
            tp2,
            f1,
            f2,
        }:
            return self._result(
                STATE_OPEN,
                "HOLD",
                0.0,
                "MATHEMATICAL_PLAN_REQUIRED",
            )

        if (
            tp2 <= tp1
            or f1 + f2 >= 1
        ):
            return self._result(
                STATE_OPEN,
                "HOLD",
                0.0,
                "MATHEMATICAL_PLAN_INVALID",
            )

        if (
            not tp1_done
            and roi_value >= tp1
        ):
            return self._result(
                STATE_TP1_DONE,
                "PARTIAL_CLOSE",
                f1,
                "TP1_REACHED",
            )

        if (
            tp1_done
            and not tp2_done
            and roi_value >= tp2
        ):
            return self._result(
                STATE_TP2_DONE,
                "PARTIAL_CLOSE",
                f2,
                "TP2_REACHED",
            )

        if tp1_done and tp2_done:
            return self._result(
                STATE_RUNNER_ACTIVE,
                "HOLD_RUNNER",
                0.0,
                "RUNNER_ACTIVE",
            )

        state = (
            STATE_TP1_DONE
            if tp1_done
            else STATE_OPEN
        )

        return self._result(
            state,
            "HOLD",
            0.0,
            "NO_TARGET_REACHED",
        )

    @staticmethod
    def _result(
        state,
        action,
        close_fraction,
        reason,
    ):
        return {
            "state": state,
            "action": action,
            "close_fraction": (
                close_fraction
            ),
            "reason": reason,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
