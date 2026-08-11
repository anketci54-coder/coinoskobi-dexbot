def evaluate_exhaustion(price_momentum, signal):
    s = signal or {}

    if s.get("freshness") != "FRESH" or s.get("coverage", 0) < 1.0:
        state = "UNKNOWN"
        signals = []
    else:
        rising = (price_momentum or 0) > 0

        signals = []

        if rising and (s.get("flow_momentum") or 0) <= 0:
            signals.append("FLOW_WEAKENING")

        if rising and (s.get("flow_acceleration") or 0) < 0:
            signals.append("FLOW_DECELERATION")

        if rising and s.get("participation_quality") == "CONCENTRATED":
            signals.append("PARTICIPATION_WEAKENING")

        if rising and s.get("liquidity_health") in {
            "DETERIORATING",
            "DETERIORATING_FAST",
            "CRITICAL",
        }:
            signals.append("LIQUIDITY_WEAKENING")

        if not rising or not signals:
            state = "NONE"
        elif len(signals) == 1:
            state = "EARLY"
        else:
            state = "CONFIRMED"

    return {
        "exhaustion_state": state,
        "signals": signals,
        "signal_count": len(signals),
        "decision_authority": False,
        "execution_authority": False,
    }
