import math


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def recommend_trailing(
    current_stop,
    price,
    runner_health=None,
    *,
    measured_stop=None,
):
    current = _number(current_stop)
    current_price = _number(price)
    measured = _number(measured_stop)

    if (
        current is None
        or current_price is None
        or current <= 0
        or current_price <= 0
    ):
        return _out(
            None,
            "UNKNOWN",
            None,
        )

    if measured is None:
        return _out(
            current,
            "MEASURED_STOP_REQUIRED",
            None,
        )

    if (
        measured <= 0
        or measured > current_price
    ):
        return _out(
            current,
            "INVALID_MEASURED_STOP",
            measured,
        )

    recommended = max(
        current,
        measured,
    )

    return _out(
        recommended,
        str(
            runner_health
            or "MEASURED_STOP"
        ),
        measured,
    )


def _out(stop, state, measured_stop):
    return {
        "recommended_stop": stop,
        "runner_health": state,
        "measured_stop": measured_stop,
        "modify_stop": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
