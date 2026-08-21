import math


def _num(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def _unknown():
    return {
        "state": "UNKNOWN",
        "buy_flow": None,
        "sell_flow": None,
        "net_flow": None,
        "spread": None,
        "velocity": None,
        "acceleration": None,
        "decision_authority": False,
        "execution_authority": False,
    }


def flow_spread(
    buy_flow,
    sell_flow,
    prev_spread=None,
    prev_velocity=None,
    freshness="FRESH",
    coverage=1.0,
):
    coverage_value = _num(coverage)

    if (
        freshness != "FRESH"
        or coverage_value is None
        or coverage_value < 1.0
    ):
        return _unknown()

    buy = _num(buy_flow)
    sell = _num(sell_flow)

    if buy is None or sell is None:
        return _unknown()

    spread = buy - sell

    previous_spread = _num(prev_spread)
    velocity = (
        None
        if previous_spread is None
        else spread - previous_spread
    )

    previous_velocity = _num(prev_velocity)
    acceleration = (
        None
        if velocity is None or previous_velocity is None
        else velocity - previous_velocity
    )

    return {
        "state": "READY",
        "buy_flow": buy,
        "sell_flow": sell,
        "net_flow": spread,
        "spread": spread,
        "velocity": velocity,
        "acceleration": acceleration,
        "decision_authority": False,
        "execution_authority": False,
    }
