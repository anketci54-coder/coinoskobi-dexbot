REQUIRED_COMPONENTS = (
    "flow",
    "acceleration",
    "market_quality",
    "wallet_flow",
    "reserve_dynamics",
    "price_impact",
)


def build_dex_signal_bundle(
    *,
    flow=None,
    acceleration=None,
    market_quality=None,
    wallet_flow=None,
    reserve_dynamics=None,
    price_impact=None,
    age_seconds=None,
    max_age_seconds=2.0,
):
    components = {
        "flow": flow,
        "acceleration": acceleration,
        "market_quality": market_quality,
        "wallet_flow": wallet_flow,
        "reserve_dynamics": reserve_dynamics,
        "price_impact": price_impact,
    }

    available = [
        name
        for name, value in components.items()
        if value is not None
    ]

    coverage = (
        len(available)
        / len(REQUIRED_COMPONENTS)
    )

    if age_seconds is None:
        freshness = "UNKNOWN"

    elif age_seconds < 0:
        freshness = "INVALID"

    elif age_seconds <= max_age_seconds:
        freshness = "FRESH"

    else:
        freshness = "STALE"

    if coverage == 1.0:
        coverage_state = "COMPLETE"

    elif coverage >= 0.67:
        coverage_state = "PARTIAL"

    else:
        coverage_state = "INSUFFICIENT"

    flow_momentum = (
        (flow or {}).get(
            "volume_imbalance"
        )
    )

    flow_acceleration = (
        (acceleration or {}).get(
            "combined_delta"
        )
    )

    participation_quality = (
        (market_quality or {}).get(
            "participation_state"
        )
    )

    volume_quality = (
        "SUSPICIOUS"
        if (market_quality or {}).get(
            "suspicious_volume"
        )
        else "NORMAL"
        if market_quality is not None
        else "UNKNOWN"
    )

    wallet_concentration = (
        (wallet_flow or {}).get(
            "concentration_state"
        )
    )

    liquidity_health = (
        (market_quality or {}).get(
            "liquidity_state"
        )
    )

    reserve_trend = (
        (reserve_dynamics or {}).get(
            "state"
        )
    )

    price_impact_health = (
        (price_impact or {}).get(
            "estimated_impact_context"
        )
    )

    return {
        "flow_momentum": flow_momentum,
        "flow_acceleration": flow_acceleration,
        "volume_quality": volume_quality,
        "participation_quality": participation_quality,
        "wallet_concentration": wallet_concentration,
        "liquidity_health": liquidity_health,
        "reserve_trend": reserve_trend,
        "price_impact_health": price_impact_health,
        "freshness": freshness,
        "coverage": coverage,
        "coverage_state": coverage_state,
        "available_components": available,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
