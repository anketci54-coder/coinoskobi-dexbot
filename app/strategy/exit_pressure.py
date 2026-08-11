def evaluate_exit_pressure(price_momentum, signal, exhaustion="NONE"):
    s = signal or {}

    if s.get("freshness") != "FRESH" or s.get("coverage", 0) < 1.0:
        state, reasons = "UNKNOWN", []
    else:
        rising = (price_momentum or 0) > 0
        reasons = []

        if rising and (s.get("flow_momentum") or 0) < 0:
            reasons.append("PRICE_FLOW_DIVERGENCE")

        if rising and s.get("participation_quality") == "CONCENTRATED":
            reasons.append("PRICE_PARTICIPATION_DIVERGENCE")

        if rising and s.get("liquidity_health") in {
            "DETERIORATING", "DETERIORATING_FAST", "CRITICAL"
        }:
            reasons.append("PRICE_LIQUIDITY_DIVERGENCE")

        if (s.get("flow_momentum") or 0) < 0 and \
           (s.get("flow_acceleration") or 0) < 0:
            reasons.append("SELL_PRESSURE_ACCELERATION")

        if exhaustion == "CONFIRMED":
            reasons.append("EXHAUSTION_CONFIRMED")

        if not reasons:
            state = "NONE"
        elif len(reasons) >= 3:
            state = "HIGH"
        else:
            state = "BUILDING"

    return {
        "exit_pressure": state,
        "reasons": reasons,
        "pressure_count": len(reasons),
        "decision_authority": False,
        "execution_authority": False,
    }
