import math


def _finite_nonnegative(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number) or number < 0:
        return None

    return number


def classify_reserve_collapse(
    *,
    previous_quote_reserve,
    current_quote_reserve,
    severe_drop_fraction=0.90,
    catastrophic_drop_fraction=0.99,
):
    previous = _finite_nonnegative(previous_quote_reserve)
    current = _finite_nonnegative(current_quote_reserve)

    result = {
        "state": "UNKNOWN",
        "previous_quote_reserve": previous,
        "current_quote_reserve": current,
        "remaining_fraction": None,
        "withdrawal_fraction": None,
        "reserve_collapse": False,
        "catastrophic_reserve_collapse": False,
        "reason": None,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }

    if previous is None or current is None or previous <= 0:
        return result

    remaining_fraction = current / previous
    withdrawal_fraction = max(
        0.0,
        min(1.0, 1.0 - remaining_fraction),
    )

    catastrophic = (
        withdrawal_fraction >= catastrophic_drop_fraction
    )
    severe = (
        withdrawal_fraction >= severe_drop_fraction
    )

    if catastrophic:
        state = "CATASTROPHIC_RESERVE_COLLAPSE"
        reason = "QUOTE_RESERVE_WITHDRAWAL_AT_LEAST_99_PERCENT"
    elif severe:
        state = "SEVERE_RESERVE_COLLAPSE"
        reason = "QUOTE_RESERVE_WITHDRAWAL_AT_LEAST_90_PERCENT"
    else:
        state = "NO_RESERVE_COLLAPSE"
        reason = None

    result.update(
        {
            "state": state,
            "remaining_fraction": remaining_fraction,
            "withdrawal_fraction": withdrawal_fraction,
            "reserve_collapse": severe,
            "catastrophic_reserve_collapse": catastrophic,
            "reason": reason,
        }
    )

    return result
