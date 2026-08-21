from dataclasses import dataclass
from typing import Optional
import math


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
    Measured-stop compatibility contract.

    The stop is calculated elsewhere from real
    mathematical evidence.

    This class only enforces:
    - highest never decreases
    - stop never loosens
    - no execution authority
    """

    def evaluate(
        self,
        *,
        current_price: float,
        highest_price: float,
        measured_stop: float,
        previous_stop: Optional[float] = None,
    ) -> TrailingStopResult:

        values = (
            current_price,
            highest_price,
            measured_stop,
        )

        if not all(
            isinstance(v, (int, float))
            and math.isfinite(float(v))
            for v in values
        ):
            raise ValueError(
                "prices must be finite numbers"
            )

        if current_price <= 0:
            raise ValueError(
                "current_price must be > 0"
            )

        if highest_price <= 0:
            raise ValueError(
                "highest_price must be > 0"
            )

        if measured_stop <= 0:
            raise ValueError(
                "measured_stop must be > 0"
            )

        new_highest = max(
            float(highest_price),
            float(current_price),
        )

        if measured_stop > new_highest:
            raise ValueError(
                "measured_stop cannot exceed highest price"
            )

        if previous_stop is not None:
            if (
                not isinstance(
                    previous_stop,
                    (int, float),
                )
                or not math.isfinite(
                    float(previous_stop)
                )
                or previous_stop < 0
            ):
                raise ValueError(
                    "previous_stop invalid"
                )

            stop_price = max(
                float(previous_stop),
                float(measured_stop),
            )
        else:
            stop_price = float(
                measured_stop
            )

        if current_price <= stop_price:
            action = ACTION_EXIT_CANDIDATE
            reason = (
                "PROTECTIVE_STOP_REACHED"
            )
        else:
            action = ACTION_HOLD
            reason = (
                "ABOVE_PROTECTIVE_STOP"
            )

        return TrailingStopResult(
            stop_price=stop_price,
            highest_price=new_highest,
            action=action,
            reason=reason,
        )
