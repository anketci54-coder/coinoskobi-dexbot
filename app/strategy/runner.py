from dataclasses import dataclass

from app.config.trading import RUNNER_FRACTION
from app.strategy.position_state import STATE_RUNNER_ACTIVE
from app.strategy.trailing_stop import (
    ACTION_EXIT_CANDIDATE,
    ProtectiveTrailingStop,
)


RUNNER_HOLD = "RUNNER_HOLD"
RUNNER_EXIT_CANDIDATE = "RUNNER_EXIT_CANDIDATE"


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
    Phase 4 pure-local runner mechanics.

    Rules:
    - runner exists only in RUNNER_ACTIVE state
    - runner fraction comes from config
    - no fixed final TP
    - protective trailing stop only
    - no market intelligence
    - no DB / paper / live execution authority
    """

    def __init__(self):
        self.trailing = ProtectiveTrailingStop()

    def evaluate(
        self,
        *,
        position_state,
        remaining_fraction,
        current_price,
        highest_price,
        trailing_factor,
        previous_stop=None,
    ):
        if position_state != STATE_RUNNER_ACTIVE:
            raise ValueError(
                "runner requires RUNNER_ACTIVE state"
            )

        if remaining_fraction < 0:
            raise ValueError(
                "remaining_fraction cannot be negative"
            )

        if abs(
            remaining_fraction - RUNNER_FRACTION
        ) > 1e-9:
            raise ValueError(
                "runner fraction does not match configured allocation"
            )

        trailing = self.trailing.evaluate(
            current_price=current_price,
            highest_price=highest_price,
            trailing_factor=trailing_factor,
            previous_stop=previous_stop,
        )

        if trailing.action == ACTION_EXIT_CANDIDATE:
            action = RUNNER_EXIT_CANDIDATE
            reason = "RUNNER_PROTECTIVE_STOP_REACHED"
        else:
            action = RUNNER_HOLD
            reason = "RUNNER_ABOVE_PROTECTIVE_STOP"

        return RunnerResult(
            state=STATE_RUNNER_ACTIVE,
            runner_fraction=remaining_fraction,
            stop_price=trailing.stop_price,
            highest_price=trailing.highest_price,
            action=action,
            reason=reason,
        )
