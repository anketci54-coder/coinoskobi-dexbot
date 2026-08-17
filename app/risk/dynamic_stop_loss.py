def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def calculate_dynamic_sl(
    *,
    flow_momentum=None,
    flow_acceleration=None,
    liquidity_health=None,
    price_impact_health=None,
    trend_health=None,
    exit_pressure=None,
):
    # Neutral baseline: 10%, but NOT a fixed SL.
    distance = 0.10

    m = _clamp(_num(flow_momentum), -1.0, 1.0)
    a = _clamp(_num(flow_acceleration), -1.0, 1.0)

    # Strong flow permits more breathing room;
    # weak flow tightens initial risk.
    distance += 0.025 * m
    distance += 0.015 * a

    liquidity = str(liquidity_health or "UNKNOWN").upper()
    impact = str(price_impact_health or "UNKNOWN").upper()
    trend = str(trend_health or "UNKNOWN").upper()
    pressure = str(exit_pressure or "UNKNOWN").upper()

    if liquidity in {"IMPROVING", "STABLE", "STABLE_OR_UNKNOWN"}:
        distance += 0.015
    elif liquidity in {"DETERIORATING", "DETERIORATING_FAST", "CRITICAL"}:
        distance -= 0.025

    if impact in {"HEALTHY", "LOW"}:
        distance += 0.010
    elif impact in {"HIGH", "UNHEALTHY", "CRITICAL"}:
        distance -= 0.020

    if trend == "STRONG":
        distance += 0.020
    elif trend == "HEALTHY":
        distance += 0.010
    elif trend == "WEAKENING":
        distance -= 0.020
    elif trend == "BREAK":
        distance -= 0.035

    if pressure == "BUILDING":
        distance -= 0.015
    elif pressure == "HIGH":
        distance -= 0.035

    # Risk envelope, not fixed stop.
    distance = _clamp(distance, 0.04, 0.18)

    return {
        "sl_distance_pct": round(distance, 6),
        "sl_multiplier": round(1.0 - distance, 6),
        "model": "DYNAMIC_SL_V1",
        "decision_authority": False,
        "live_authority": False,
    }
