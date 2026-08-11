def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def analyze_flow_acceleration(
    *,
    short_flow,
    long_flow,
):
    short_flow = short_flow or {}
    long_flow = long_flow or {}

    short_count = _number(
        short_flow.get("count_imbalance")
    )
    long_count = _number(
        long_flow.get("count_imbalance")
    )

    short_volume = _number(
        short_flow.get("volume_imbalance")
    )
    long_volume = _number(
        long_flow.get("volume_imbalance")
    )

    count_delta = short_count - long_count
    volume_delta = short_volume - long_volume

    combined_delta = (
        count_delta + volume_delta
    ) / 2.0

    if combined_delta >= 0.20:
        state = "ACCELERATING_BUY"

    elif combined_delta <= -0.20:
        state = "ACCELERATING_SELL"

    elif combined_delta > 0.05:
        state = "IMPROVING"

    elif combined_delta < -0.05:
        state = "DETERIORATING"

    else:
        state = "STABLE"

    return {
        "short_count_imbalance": short_count,
        "long_count_imbalance": long_count,
        "short_volume_imbalance": short_volume,
        "long_volume_imbalance": long_volume,
        "count_delta": count_delta,
        "volume_delta": volume_delta,
        "combined_delta": combined_delta,
        "state": state,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
