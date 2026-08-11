from dataclasses import dataclass, replace

from app.config.trading import (
    TP1_CLOSE_FRACTION,
    TP2_CLOSE_FRACTION,
    TP3_CLOSE_FRACTION,
)


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

STATE_ORDER = {
    STATE_OPEN: 0,
    STATE_TP1_DONE: 1,
    STATE_TP2_DONE: 2,
    STATE_TP3_DONE: 3,
    STATE_RUNNER_ACTIVE: 4,
    STATE_CLOSED: 5,
}

TARGET_CLOSE_FRACTION = {
    STATE_TP1_DONE: TP1_CLOSE_FRACTION,
    STATE_TP2_DONE: TP2_CLOSE_FRACTION,
    STATE_TP3_DONE: TP3_CLOSE_FRACTION,
}


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
        if self.state in (
            STATE_TP3_DONE,
            STATE_RUNNER_ACTIVE,
        ):
            return self.remaining_fraction
        return 0.0


class PositionStateMachine:
    """
    Pure-local mechanical position state contract.

    No DB writes.
    No paper execution.
    No live execution.
    No wallet authority.
    """

    def initial(self):
        return PositionState()

    def apply_tp(self, position, target_state):
        self.validate(position)

        expected = {
            STATE_OPEN: STATE_TP1_DONE,
            STATE_TP1_DONE: STATE_TP2_DONE,
            STATE_TP2_DONE: STATE_TP3_DONE,
        }.get(position.state)

        if target_state != expected:
            return {
                "applied": False,
                "reason": "INVALID_OR_DUPLICATE_TRANSITION",
                "position": position,
            }

        close_fraction = TARGET_CLOSE_FRACTION[target_state]

        remaining = position.remaining_fraction - close_fraction
        realized = position.realized_fraction + close_fraction

        if remaining < -1e-9:
            raise ValueError("remaining_fraction below zero")

        flags = {
            "tp1_done": position.tp1_done,
            "tp2_done": position.tp2_done,
            "tp3_done": position.tp3_done,
        }

        if target_state == STATE_TP1_DONE:
            flags["tp1_done"] = True
        elif target_state == STATE_TP2_DONE:
            flags["tp2_done"] = True
        elif target_state == STATE_TP3_DONE:
            flags["tp3_done"] = True

        updated = replace(
            position,
            state=target_state,
            remaining_fraction=round(remaining, 12),
            realized_fraction=round(realized, 12),
            **flags,
        )

        self.validate(updated)

        return {
            "applied": True,
            "reason": target_state,
            "close_fraction": close_fraction,
            "position": updated,
        }

    def activate_runner(self, position):
        self.validate(position)

        if position.state != STATE_TP3_DONE:
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
            raise ValueError("invalid state")

        values = (
            position.original_fraction,
            position.remaining_fraction,
            position.realized_fraction,
        )

        if any(value < -1e-9 for value in values):
            raise ValueError("negative fraction")

        total = (
            position.remaining_fraction
            + position.realized_fraction
        )

        if abs(total - position.original_fraction) > 1e-9:
            raise ValueError("fraction conservation violated")

        if position.tp2_done and not position.tp1_done:
            raise ValueError("TP2 without TP1")

        if position.tp3_done and not (
            position.tp1_done and position.tp2_done
        ):
            raise ValueError("TP3 without TP1/TP2")

        if position.state == STATE_TP1_DONE and not position.tp1_done:
            raise ValueError("TP1 state mismatch")

        if position.state == STATE_TP2_DONE and not (
            position.tp1_done and position.tp2_done
        ):
            raise ValueError("TP2 state mismatch")

        if position.state in (
            STATE_TP3_DONE,
            STATE_RUNNER_ACTIVE,
        ):
            if not (
                position.tp1_done
                and position.tp2_done
                and position.tp3_done
            ):
                raise ValueError("runner state mismatch")

        if position.state == STATE_CLOSED:
            if abs(position.remaining_fraction) > 1e-9:
                raise ValueError("closed position has remainder")

        return True

    def authority(self):
        return {
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
