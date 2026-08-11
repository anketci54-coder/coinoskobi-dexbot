def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def flow_spread(
    buy_flow,
    sell_flow,
    prev_spread=None,
    prev_velocity=None,
    freshness="FRESH",
    coverage=1.0,
):
    if freshness != "FRESH" or coverage < 1.0:
        return {
            "state": "UNKNOWN",
            "net_flow": None,
            "spread": None,
            "velocity": None,
            "acceleration": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    buy = _num(buy_flow)
    sell = _num(sell_flow)

    spread = buy - sell
    velocity = (
        None if prev_spread is None
        else spread - _num(prev_spread)
    )
    acceleration = (
        None
        if velocity is None or prev_velocity is None
        else velocity - _num(prev_velocity)
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
