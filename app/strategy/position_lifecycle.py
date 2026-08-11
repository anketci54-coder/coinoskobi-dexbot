from app.config.trading import (
    TP1_ROI,
    TP1_CLOSE_FRACTION,
    TP2_ROI,
    TP2_CLOSE_FRACTION,
    TP3_ROI,
    TP3_CLOSE_FRACTION,
    RUNNER_FRACTION,
)


STATE_OPEN = "OPEN"
STATE_TP1_DONE = "TP1_DONE"
STATE_TP2_DONE = "TP2_DONE"
STATE_TP3_DONE = "TP3_DONE"
STATE_RUNNER_ACTIVE = "RUNNER_ACTIVE"


class PositionLifecycleEngine:
    """
    Pure-local mechanical position lifecycle contract.

    No DB writes.
    No paper execution.
    No live execution.
    No wallet authority.
    No external calls.
    """

    def __init__(self):
        total = (
            TP1_CLOSE_FRACTION
            + TP2_CLOSE_FRACTION
            + TP3_CLOSE_FRACTION
            + RUNNER_FRACTION
        )

        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                "position lifecycle fractions must sum to 1.0"
            )

    def evaluate(
        self,
        *,
        roi,
        tp1_done=False,
        tp2_done=False,
        tp3_done=False,
    ):
        if roi is None:
            return self._result(
                state=STATE_OPEN,
                action="HOLD",
                close_fraction=0.0,
                reason="ROI_UNKNOWN",
            )

        roi = float(roi)

        # Advance only one lifecycle stage per evaluation.
        if not tp1_done and roi >= TP1_ROI:
            return self._result(
                state=STATE_TP1_DONE,
                action="PARTIAL_CLOSE",
                close_fraction=TP1_CLOSE_FRACTION,
                reason="TP1_REACHED",
            )

        if (
            tp1_done
            and not tp2_done
            and roi >= TP2_ROI
        ):
            return self._result(
                state=STATE_TP2_DONE,
                action="PARTIAL_CLOSE",
                close_fraction=TP2_CLOSE_FRACTION,
                reason="TP2_REACHED",
            )

        if (
            tp1_done
            and tp2_done
            and not tp3_done
            and roi >= TP3_ROI
        ):
            return self._result(
                state=STATE_TP3_DONE,
                action="PARTIAL_CLOSE",
                close_fraction=TP3_CLOSE_FRACTION,
                reason="TP3_REACHED",
            )

        if tp1_done and tp2_done and tp3_done:
            return self._result(
                state=STATE_RUNNER_ACTIVE,
                action="HOLD_RUNNER",
                close_fraction=0.0,
                reason="RUNNER_ACTIVE",
            )

        state = STATE_OPEN

        if tp1_done:
            state = STATE_TP1_DONE

        if tp2_done:
            state = STATE_TP2_DONE

        if tp3_done:
            state = STATE_TP3_DONE

        return self._result(
            state=state,
            action="HOLD",
            close_fraction=0.0,
            reason="NO_TARGET_REACHED",
        )

    @staticmethod
    def _result(
        *,
        state,
        action,
        close_fraction,
        reason,
    ):
        return {
            "state": state,
            "action": action,
            "close_fraction": close_fraction,
            "reason": reason,

            # Phase 4B is mechanical/advisory only.
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
