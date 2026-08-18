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
    atr_pct=None,
):
    """Calculate a bounded dynamic protection distance.

    Measured ATR, when available, is the volatility anchor. Missing ATR is
    never invented: the existing market-state model supplies a bounded
    fallback until real volatility evidence arrives.
    """
    measured_atr = _num(atr_pct, 0.0)
    if measured_atr > 0:
        # ATR is expected as a ratio (0.05 == 5%). Give volatile assets
        # enough room while keeping the initial risk envelope bounded.
        distance = _clamp(measured_atr * 1.75, 0.025, 0.22)
    else:
        distance = 0.10

    m = _clamp(_num(flow_momentum), -1.0, 1.0)
    a = _clamp(_num(flow_acceleration), -1.0, 1.0)
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

    distance = _clamp(distance, 0.025, 0.22)

    return {
        "sl_distance_pct": round(distance, 6),
        "sl_multiplier": round(1.0 - distance, 6),
        "atr_pct": round(measured_atr, 6) if measured_atr > 0 else None,
        "volatility_source": "MEASURED_ATR" if measured_atr > 0 else "MARKET_STATE",
        "model": "DYNAMIC_SL_V1",
        "decision_authority": False,
        "live_authority": False,
    }
