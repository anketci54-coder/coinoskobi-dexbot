def _number(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bounded(v, lo, hi):
    v = _number(v)
    if v is None or v < lo or v > hi:
        return None
    return v


def build_hybrid_exit_runtime_input(
    *,
    position_state=None,
    signal_bundle=None,
    trend_health=None,
    exit_pressure=None,
    hard_block=False,
    sellability=None,
):
    pos = dict(position_state or {})
    sig = dict(signal_bundle or {})

    trend_src = (
        trend_health.get("trend_health")
        if isinstance(trend_health, dict)
        else trend_health
    )
    pressure_src = (
        exit_pressure.get("exit_pressure")
        if isinstance(exit_pressure, dict)
        else exit_pressure
    )

    freshness = sig.get("freshness", "UNKNOWN")
    coverage = _number(sig.get("coverage"))
    ready = (
        freshness == "FRESH"
        and coverage is not None
        and coverage >= 1.0
    )

    if ready:
        liquidity = _bounded(sig.get("liquidity_health"), 0.0, 1.0)
        momentum = _bounded(sig.get("flow_momentum"), -1.0, 1.0)
        acceleration = _bounded(sig.get("flow_acceleration"), -1.0, 1.0)
        trend = _bounded(trend_src, 0.0, 1.0)
        pressure = _bounded(pressure_src, 0.0, 1.0)
        impact = _bounded(sig.get("price_impact_health"), 0.0, 1.0)
    else:
        liquidity = momentum = acceleration = None
        trend = pressure = impact = None

    return {
        "entry_price": pos.get("entry_price"),
        "current_price": pos.get("current_price"),
        "highest_price": pos.get("highest_price"),
        "static_sl_price": pos.get("sl_price"),

        "hard_block": bool(hard_block),
        "sellability": sellability or "SELLABILITY_UNKNOWN",

        "liquidity_health": liquidity,
        "flow_momentum": momentum,
        "flow_acceleration": acceleration,
        "trend_health": trend,
        "exit_pressure": pressure,
        "price_impact_health": impact,

        # Unit is not guessed.
        "atr_pct": None,

        "evidence_ready": ready,
        "freshness": freshness,
        "coverage": coverage,

        "source_liquidity_health": sig.get("liquidity_health"),
        "source_trend_health": trend_src,
        "source_exit_pressure": pressure_src,
        "source_price_impact_health": sig.get("price_impact_health"),

        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
