def _positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(value, 0.0)


def _change(current, previous):
    current = _positive(current)
    previous = _positive(previous)

    if previous <= 0:
        return None

    return (
        current - previous
    ) / previous


def analyze_reserve_dynamics(
    *,
    reserve0,
    reserve1,
    previous_reserve0=None,
    previous_reserve1=None,
):
    reserve0 = _positive(reserve0)
    reserve1 = _positive(reserve1)

    change0 = None
    change1 = None

    if previous_reserve0 is not None:
        change0 = _change(
            reserve0,
            previous_reserve0,
        )

    if previous_reserve1 is not None:
        change1 = _change(
            reserve1,
            previous_reserve1,
        )

    known = [
        value
        for value in (change0, change1)
        if value is not None
    ]

    worst_change = (
        min(known)
        if known
        else None
    )

    best_change = (
        max(known)
        if known
        else None
    )

    if reserve0 <= 0 or reserve1 <= 0:
        state = "BROKEN_DEPTH"

    elif (
        worst_change is not None
        and worst_change <= -0.30
    ):
        state = "LIQUIDITY_SHOCK"

    elif (
        worst_change is not None
        and worst_change <= -0.10
    ):
        state = "DETERIORATING"

    elif (
        best_change is not None
        and best_change >= 0.10
    ):
        state = "IMPROVING"

    elif known:
        state = "STABLE"

    else:
        state = "UNKNOWN"

    return {
        "reserve0": reserve0,
        "reserve1": reserve1,
        "reserve0_change_pct": change0,
        "reserve1_change_pct": change1,
        "worst_change_pct": worst_change,
        "state": state,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
