def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value):
    if isinstance(value, bool):
        return value
    return None


def evaluate_exit_context(
    position_state,
    runner_state,
    signal_bundle,
):
    """
    Phase 6A baseline.

    Bu katman:
    - Phase 4 position/runner state okur
    - Phase 5 DEX signal bundle okur
    - exit context uretir
    - trade/decision/execution authority tasimaz

    Threshold tuning Phase 6'nin sonraki alt fazlarina aittir.
    """

    position_state = position_state or {}
    runner_state = runner_state or {}
    signal_bundle = signal_bundle or {}

    freshness = signal_bundle.get("freshness")
    coverage = _number(signal_bundle.get("coverage"))

    reserve_trend = signal_bundle.get("reserve_trend")
    liquidity_health = signal_bundle.get("liquidity_health")
    participation_quality = signal_bundle.get(
        "participation_quality"
    )
    wallet_concentration = signal_bundle.get(
        "wallet_concentration"
    )
    price_impact_health = signal_bundle.get(
        "price_impact_health"
    )

    flow_momentum = _number(
        signal_bundle.get("flow_momentum")
    )

    flow_acceleration = _number(
        signal_bundle.get("flow_acceleration")
    )

    trailing_active = _bool(
        runner_state.get("trailing_active")
    )

    tp1_hit = _bool(
        position_state.get("tp1_hit")
    )

    tp2_hit = _bool(
        position_state.get("tp2_hit")
    )

    tp3_hit = _bool(
        position_state.get("tp3_hit")
    )

    data_ready = (
        freshness == "FRESH"
        and coverage is not None
        and coverage >= 1.0
    )

    structural_risk = (
        reserve_trend in {
            "DETERIORATING",
            "DROPPING_FAST",
            "BREAK",
        }
        or liquidity_health in {
            "DETERIORATING",
            "DETERIORATING_FAST",
            "CRITICAL",
        }
        or price_impact_health in {
            "HIGH",
            "CRITICAL",
            "UNHEALTHY",
        }
    )

    flow_weakness = (
        flow_momentum is not None
        and flow_momentum < 0
        and flow_acceleration is not None
        and flow_acceleration <= 0
    )

    participation_warning = (
        participation_quality == "CONCENTRATED"
        or wallet_concentration == "CONCENTRATED"
    )

    if not data_ready:
        state = "UNKNOWN"

    elif structural_risk:
        state = "EXIT_PRESSURE"

    elif flow_weakness and participation_warning:
        state = "WEAKENING"

    elif (
        flow_momentum is not None
        and flow_momentum > 0
        and flow_acceleration is not None
        and flow_acceleration >= 0
    ):
        state = "HOLDING"

    else:
        state = "NEUTRAL"

    return {
        "state": state,
        "data_ready": data_ready,
        "freshness": freshness,
        "coverage": coverage,
        "flow_momentum": flow_momentum,
        "flow_acceleration": flow_acceleration,
        "reserve_trend": reserve_trend,
        "liquidity_health": liquidity_health,
        "participation_quality": participation_quality,
        "wallet_concentration": wallet_concentration,
        "price_impact_health": price_impact_health,
        "trailing_active": trailing_active,
        "tp1_hit": tp1_hit,
        "tp2_hit": tp2_hit,
        "tp3_hit": tp3_hit,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
