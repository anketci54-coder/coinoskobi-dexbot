"""Hybrid Exit runtime normalization adapter."""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value, low, high):
    return max(low, min(high, value))


LIQUIDITY_HEALTH_MAP = {
    "HEALTHY": 1.0, "STRONG": 1.0, "STABLE": 0.80,
    "STABLE_OR_UNKNOWN": 0.50, "UNKNOWN": 0.50,
    "DETERIORATING": 0.30, "DETERIORATING_FAST": 0.15,
    "DRAINING": 0.05, "CRITICAL": 0.0, "COLLAPSE": 0.0,
}
TREND_HEALTH_MAP = {
    "STRONG": 1.0, "HEALTHY": 0.80, "WEAKENING": 0.35,
    "BREAK": 0.0, "UNKNOWN": 0.50,
}
EXIT_PRESSURE_MAP = {
    "NONE": 0.0, "BUILDING": 0.50, "HIGH": 1.0, "UNKNOWN": 0.0,
}
PRICE_IMPACT_HEALTH_MAP = {
    "HEALTHY": 1.0, "LOW": 1.0, "NORMAL": 0.80, "MODERATE": 0.60,
    "UNKNOWN": 0.50, "STABLE_OR_UNKNOWN": 0.50, "HIGH": 0.20,
    "UNHEALTHY": 0.10, "CRITICAL": 0.0,
}


def _category_score(value, mapping, neutral):
    if value is None or isinstance(value, bool):
        return neutral
    numeric = _number(value)
    if numeric is not None:
        return _clamp(numeric, 0.0, 1.0)
    return mapping.get(str(value).strip().upper(), neutral)


def _signed_score(value):
    if value is None or isinstance(value, bool):
        return 0.0
    numeric = _number(value)
    if numeric is None:
        return 0.0
    return _clamp(numeric, -1.0, 1.0)


def build_hybrid_exit_runtime_input(
    *, position_state=None, signal_bundle=None, trend_health=None,
    exit_pressure=None, hard_block=False, sellability=None,
):
    position = dict(position_state or {})
    signal = dict(signal_bundle or {})
    trend = trend_health.get("trend_health") if isinstance(trend_health, dict) else trend_health
    pressure = exit_pressure.get("exit_pressure") if isinstance(exit_pressure, dict) else exit_pressure
    freshness = signal.get("freshness", "UNKNOWN")
    coverage = _number(signal.get("coverage"))
    evidence_ready = freshness == "FRESH" and coverage is not None and coverage >= 1.0

    if evidence_ready:
        liquidity_score = _category_score(signal.get("liquidity_health"), LIQUIDITY_HEALTH_MAP, 0.50)
        momentum_score = _signed_score(signal.get("flow_momentum"))
        acceleration_score = _signed_score(signal.get("flow_acceleration"))
        trend_score = _category_score(trend, TREND_HEALTH_MAP, 0.50)
        pressure_score = _category_score(pressure, EXIT_PRESSURE_MAP, 0.0)
        impact_score = _category_score(signal.get("price_impact_health"), PRICE_IMPACT_HEALTH_MAP, 0.50)
    else:
        liquidity_score = 0.50
        momentum_score = 0.0
        acceleration_score = 0.0
        trend_score = 0.50
        pressure_score = 0.0
        impact_score = 0.50

    atr_pct = None
    if evidence_ready:
        for key in ("atr_pct", "atr_percent", "normalized_atr", "volatility_pct"):
            value = _number(signal.get(key))
            if value is not None and value > 0:
                atr_pct = value / 100.0 if value > 1.0 else value
                break

    return {
        "entry_price": position.get("entry_price"),
        "current_price": position.get("current_price"),
        "highest_price": position.get("highest_price"),
        # Compatibility name; semantically this is the current persisted
        # dynamic protection floor, not a static stop authority.
        "static_sl_price": position.get("sl_price"),
        "hard_block": bool(hard_block),
        "sellability": sellability or "SELLABILITY_UNKNOWN",
        "liquidity_health": liquidity_score,
        "flow_momentum": momentum_score,
        "flow_acceleration": acceleration_score,
        "trend_health": trend_score,
        "exit_pressure": pressure_score,
        "price_impact_health": impact_score,
        "atr_pct": atr_pct,
        "evidence_ready": evidence_ready,
        "freshness": freshness,
        "coverage": coverage,
        "source_liquidity_health": signal.get("liquidity_health"),
        "source_trend_health": trend,
        "source_exit_pressure": pressure,
        "source_price_impact_health": signal.get("price_impact_health"),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
