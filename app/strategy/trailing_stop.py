from dataclasses import dataclass
from typing import Optional


ACTION_HOLD = "HOLD"
ACTION_EXIT_CANDIDATE = "EXIT_CANDIDATE"


@dataclass(frozen=True)
class TrailingStopResult:
    stop_price: float
    highest_price: float
    action: str
    reason: str
    decision_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    wallet_authority: bool = False
    execution_authority: bool = False


class ProtectiveTrailingStop:
    """
    Pure-local Phase 4 mechanical trailing-stop contract.

    Invariants:
    - highest_price never decreases
    - stop_price never decreases
    - stop cannot be negative
    - this module has no execution authority
    """

    def evaluate(
        self,
        *,
        current_price: float,
        highest_price: float,
        trailing_factor: float,
        previous_stop: Optional[float] = None,
    ) -> TrailingStopResult:

        if current_price <= 0:
            raise ValueError("current_price must be > 0")

        if highest_price <= 0:
            raise ValueError("highest_price must be > 0")

        if not 0 < trailing_factor <= 1:
            raise ValueError(
                "trailing_factor must be > 0 and <= 1"
            )

        if previous_stop is not None and previous_stop < 0:
            raise ValueError("previous_stop cannot be negative")

        new_highest = max(
            highest_price,
            current_price,
        )

        candidate_stop = (
            new_highest * trailing_factor
        )

        if previous_stop is None:
            stop_price = candidate_stop
        else:
            # Core monotonic invariant:
            # protective stop can tighten, never loosen.
            stop_price = max(
                previous_stop,
                candidate_stop,
            )

        if current_price <= stop_price:
            action = ACTION_EXIT_CANDIDATE
            reason = "PROTECTIVE_STOP_REACHED"
        else:
            action = ACTION_HOLD
            reason = "ABOVE_PROTECTIVE_STOP"

        return TrailingStopResult(
            stop_price=stop_price,
            highest_price=new_highest,
            action=action,
            reason=reason,
        )
