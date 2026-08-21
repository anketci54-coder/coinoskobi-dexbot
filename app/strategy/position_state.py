from dataclasses import dataclass, replace
import math


STATE_OPEN = "OPEN"
STATE_TP1_DONE = "TP1_DONE"
STATE_TP2_DONE = "TP2_DONE"
STATE_TP3_DONE = "TP3_DONE"
STATE_RUNNER_ACTIVE = "RUNNER_ACTIVE"
STATE_CLOSED = "CLOSED"


VALID_STATES = (
    STATE_OPEN,
    STATE_TP1_DONE,
    STATE_TP2_DONE,
    STATE_TP3_DONE,
    STATE_RUNNER_ACTIVE,
    STATE_CLOSED,
)


def _fraction(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    if value <= 0 or value > 1:
        return None

    return value


@dataclass(frozen=True)
class PositionState:
    state: str = STATE_OPEN
    original_fraction: float = 1.0
    remaining_fraction: float = 1.0
    realized_fraction: float = 0.0
    tp1_done: bool = False
    tp2_done: bool = False
    tp3_done: bool = False

    @property
    def runner_fraction(self):
        if self.state == STATE_RUNNER_ACTIVE:
            return self.remaining_fraction

        return 0.0


class PositionStateMachine:
    """
    Compatibility-only mechanical state machine.

    Realization size must be supplied by the
    canonical mathematical trade plan.
    """

    def initial(self):
        return PositionState()

    def apply_tp(
        self,
        position,
        target_state,
        *,
        close_fraction=None,
    ):
        self.validate(position)

        expected = {
            STATE_OPEN: STATE_TP1_DONE,
            STATE_TP1_DONE: STATE_TP2_DONE,
        }.get(position.state)

        if target_state == STATE_TP3_DONE:
            return {
                "applied": False,
                "reason": (
                    "TP3_IS_RUNNER_NOT_FIXED_TARGET"
                ),
                "position": position,
            }

        if target_state != expected:
            return {
                "applied": False,
                "reason": (
                    "INVALID_OR_DUPLICATE_TRANSITION"
                ),
                "position": position,
            }

        fraction = _fraction(
            close_fraction
        )

        if fraction is None:
            return {
                "applied": False,
                "reason": (
                    "MEASURED_CLOSE_FRACTION_REQUIRED"
                ),
                "position": position,
            }

        if (
            fraction
            > position.remaining_fraction
        ):
            return {
                "applied": False,
                "reason": (
                    "CLOSE_FRACTION_EXCEEDS_REMAINING"
                ),
                "position": position,
            }

        remaining = (
            position.remaining_fraction
            - fraction
        )
        realized = (
            position.realized_fraction
            + fraction
        )

        flags = {
            "tp1_done": position.tp1_done,
            "tp2_done": position.tp2_done,
            "tp3_done": False,
        }

        if target_state == STATE_TP1_DONE:
            flags["tp1_done"] = True

        elif target_state == STATE_TP2_DONE:
            flags["tp2_done"] = True

        updated = replace(
            position,
            state=target_state,
            remaining_fraction=round(
                remaining,
                12,
            ),
            realized_fraction=round(
                realized,
                12,
            ),
            **flags,
        )

        self.validate(updated)

        return {
            "applied": True,
            "reason": target_state,
            "close_fraction": fraction,
            "position": updated,
        }

    def activate_runner(
        self,
        position,
    ):
        self.validate(position)

        if (
            position.state
            != STATE_TP2_DONE
        ):
            return {
                "applied": False,
                "reason": "RUNNER_NOT_READY",
                "position": position,
            }

        updated = replace(
            position,
            state=STATE_RUNNER_ACTIVE,
        )

        self.validate(updated)

        return {
            "applied": True,
            "reason": STATE_RUNNER_ACTIVE,
            "position": updated,
        }

    def close(self, position):
        self.validate(position)

        if position.state == STATE_CLOSED:
            return {
                "applied": False,
                "reason": "ALREADY_CLOSED",
                "position": position,
            }

        updated = replace(
            position,
            state=STATE_CLOSED,
            realized_fraction=round(
                position.realized_fraction
                + position.remaining_fraction,
                12,
            ),
            remaining_fraction=0.0,
        )

        self.validate(updated)

        return {
            "applied": True,
            "reason": STATE_CLOSED,
            "position": updated,
        }

    def validate(self, position):
        if position.state not in VALID_STATES:
            raise ValueError(
                "invalid state"
            )

        values = (
            position.original_fraction,
            position.remaining_fraction,
            position.realized_fraction,
        )

        if not all(
            isinstance(v, (int, float))
            and math.isfinite(float(v))
            for v in values
        ):
            raise ValueError(
                "invalid fraction"
            )

        if position.original_fraction <= 0:
            raise ValueError(
                "original_fraction must be positive"
            )

        if (
            position.remaining_fraction < 0
            or position.realized_fraction < 0
        ):
            raise ValueError(
                "fraction cannot be negative"
            )

        if abs(
            (
                position.remaining_fraction
                + position.realized_fraction
            )
            - position.original_fraction
        ) > 1e-9:
            raise ValueError(
                "fraction conservation failed"
            )

        if (
            position.tp2_done
            and not position.tp1_done
        ):
            raise ValueError(
                "tp2 requires tp1"
            )

        if position.tp3_done:
            raise ValueError(
                "fixed tp3 is not supported"
            )

        return True

    @staticmethod
    def authority():
        return {
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
