from dataclasses import dataclass

from app.strategy.position_state import (
    STATE_RUNNER_ACTIVE,
)
from app.strategy.trailing_stop import (
    ACTION_EXIT_CANDIDATE,
    ProtectiveTrailingStop,
)


RUNNER_HOLD = "RUNNER_HOLD"
RUNNER_EXIT_CANDIDATE = (
    "RUNNER_EXIT_CANDIDATE"
)


@dataclass(frozen=True)
class RunnerResult:
    state: str
    runner_fraction: float
    stop_price: float
    highest_price: float
    action: str
    reason: str

    decision_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    wallet_authority: bool = False
    execution_authority: bool = False


class RunnerEngine:
    """
    Compatibility-only runner mechanics.

    The remaining position is the runner.
    No fixed runner fraction.
    No fixed final TP.
    No fixed trailing percentage.
    """

    def __init__(self):
        self.trailing = (
            ProtectiveTrailingStop()
        )

    def evaluate(
        self,
        *,
        position_state,
        remaining_fraction,
        current_price,
        highest_price,
        measured_stop,
        previous_stop=None,
    ):
        if (
            position_state
            != STATE_RUNNER_ACTIVE
        ):
            raise ValueError(
                "runner requires RUNNER_ACTIVE state"
            )

        if not (
            0 < float(
                remaining_fraction
            ) <= 1
        ):
            raise ValueError(
                "remaining_fraction must be > 0 and <= 1"
            )

        trailing = self.trailing.evaluate(
            current_price=current_price,
            highest_price=highest_price,
            measured_stop=measured_stop,
            previous_stop=previous_stop,
        )

        if (
            trailing.action
            == ACTION_EXIT_CANDIDATE
        ):
            action = (
                RUNNER_EXIT_CANDIDATE
            )
            reason = (
                "RUNNER_PROTECTIVE_STOP_REACHED"
            )
        else:
            action = RUNNER_HOLD
            reason = (
                "RUNNER_ABOVE_PROTECTIVE_STOP"
            )

        return RunnerResult(
            state=STATE_RUNNER_ACTIVE,
            runner_fraction=float(
                remaining_fraction
            ),
            stop_price=trailing.stop_price,
            highest_price=(
                trailing.highest_price
            ),
            action=action,
            reason=reason,
        )
