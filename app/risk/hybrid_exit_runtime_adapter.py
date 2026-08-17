"""
Hybrid Exit runtime normalization adapter.

Purpose:
- translate existing categorical runtime/strategy evidence into the
  numeric domain expected by evaluate_hybrid_exit()
- preserve UNKNOWN/missing evidence as neutral values
- carry no decision, paper, live, wallet, or execution authority
- perform no DB write, provider call, RPC call, signing, or execution

This adapter does NOT call evaluate_hybrid_exit().
It only prepares its bounded input contract.
"""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value, low, high):
    return max(low, min(high, value))


LIQUIDITY_HEALTH_MAP = {
    "HEALTHY": 1.0,
    "STRONG": 1.0,
    "STABLE": 0.80,
    "STABLE_OR_UNKNOWN": 0.50,
    "UNKNOWN": 0.50,
    "DETERIORATING": 0.30,
    "DETERIORATING_FAST": 0.15,
    "DRAINING": 0.05,
    "CRITICAL": 0.0,
    "COLLAPSE": 0.0,
}

TREND_HEALTH_MAP = {
    "STRONG": 1.0,
    "HEALTHY": 0.80,
    "WEAKENING": 0.35,
    "BREAK": 0.0,
    "UNKNOWN": 0.50,
}

EXIT_PRESSURE_MAP = {
    "NONE": 0.0,
    "BUILDING": 0.50,
    "HIGH": 1.0,
    "UNKNOWN": 0.0,
}

PRICE_IMPACT_HEALTH_MAP = {
    "HEALTHY": 1.0,
    "LOW": 1.0,
    "NORMAL": 0.80,
    "MODERATE": 0.60,
    "UNKNOWN": 0.50,
    "STABLE_OR_UNKNOWN": 0.50,
    "HIGH": 0.20,
    "UNHEALTHY": 0.10,
    "CRITICAL": 0.0,
}


def _category_score(value, mapping, neutral):
    if value is None:
        return neutral

    if isinstance(value, bool):
        return neutral

    numeric = _number(value)

    if numeric is not None:
        return _clamp(
            numeric,
            0.0,
            1.0,
        )

    key = str(value).strip().upper()

    return mapping.get(
        key,
        neutral,
    )


def _signed_score(value):
    if value is None:
        return 0.0

    if isinstance(value, bool):
        return 0.0

    numeric = _number(value)

    if numeric is None:
        return 0.0

    return _clamp(
        numeric,
        -1.0,
        1.0,
    )


def build_hybrid_exit_runtime_input(
    *,
    position_state=None,
    signal_bundle=None,
    trend_health=None,
    exit_pressure=None,
    hard_block=False,
    sellability=None,
):
    """
    Build the normalized input contract consumed later by
    evaluate_hybrid_exit().

    UNKNOWN policy:
    - categorical health -> neutral 0.50
    - exit pressure -> 0.0
    - signed flow -> 0.0

    These defaults mean "no additional evidence", not approval.
    Hard safety remains external and explicit.
    """

    position = dict(
        position_state or {}
    )

    signal = dict(
        signal_bundle or {}
    )

    trend = (
        trend_health.get("trend_health")
        if isinstance(trend_health, dict)
        else trend_health
    )

    pressure = (
        exit_pressure.get("exit_pressure")
        if isinstance(exit_pressure, dict)
        else exit_pressure
    )

    freshness = signal.get(
        "freshness",
        "UNKNOWN",
    )

    coverage = _number(
        signal.get("coverage")
    )

    evidence_ready = (
        freshness == "FRESH"
        and coverage is not None
        and coverage >= 1.0
    )

    if evidence_ready:
        liquidity_score = _category_score(
            signal.get("liquidity_health"),
            LIQUIDITY_HEALTH_MAP,
            0.50,
        )

        momentum_score = _signed_score(
            signal.get("flow_momentum")
        )

        acceleration_score = _signed_score(
            signal.get("flow_acceleration")
        )

        trend_score = _category_score(
            trend,
            TREND_HEALTH_MAP,
            0.50,
        )

        pressure_score = _category_score(
            pressure,
            EXIT_PRESSURE_MAP,
            0.0,
        )

        impact_score = _category_score(
            signal.get("price_impact_health"),
            PRICE_IMPACT_HEALTH_MAP,
            0.50,
        )

    else:
        liquidity_score = 0.50
        momentum_score = 0.0
        acceleration_score = 0.0
        trend_score = 0.50
        pressure_score = 0.0
        impact_score = 0.50

    return {
        "entry_price": position.get(
            "entry_price"
        ),
        "current_price": position.get(
            "current_price"
        ),
        "highest_price": position.get(
            "highest_price"
        ),
        "static_sl_price": position.get(
            "sl_price"
        ),
        "hard_block": bool(
            hard_block
        ),
        "sellability": (
            sellability
            or "SELLABILITY_UNKNOWN"
        ),
        "liquidity_health": liquidity_score,
        "flow_momentum": momentum_score,
        "flow_acceleration": acceleration_score,
        "trend_health": trend_score,
        "exit_pressure": pressure_score,
        "price_impact_health": impact_score,
        "evidence_ready": evidence_ready,
        "freshness": freshness,
        "coverage": coverage,
        "source_liquidity_health": signal.get(
            "liquidity_health"
        ),
        "source_trend_health": trend,
        "source_exit_pressure": pressure,
        "source_price_impact_health": signal.get(
            "price_impact_health"
        ),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
