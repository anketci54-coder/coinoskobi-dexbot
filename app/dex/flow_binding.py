def bind_flow_context(signal_bundle, regime, agreement):
    s = signal_bundle or {}
    r = regime or {}
    a = agreement or {}

    freshness = s.get("freshness")
    coverage = s.get("coverage")

    ready = (
        freshness == "FRESH"
        and coverage is not None
        and coverage >= 1.0
        and r.get("market_regime") != "UNKNOWN"
        and a.get("agreement") != "UNKNOWN"
    )

    return {
        "flow_context_ready": ready,
        "market_regime": r.get("market_regime", "UNKNOWN"),
        "flow_agreement": a.get("agreement", "UNKNOWN"),
        "agreement_score": a.get("agreement_score"),
        "freshness": freshness,
        "coverage": coverage,
        "flow_momentum": s.get("flow_momentum"),
        "flow_acceleration": s.get("flow_acceleration"),
        "participation_quality": s.get("participation_quality"),
        "wallet_concentration": s.get("wallet_concentration"),
        "liquidity_health": s.get("liquidity_health"),
        "reserve_trend": s.get("reserve_trend"),
        "price_impact_health": s.get("price_impact_health"),
        "decision_authority": False,
        "execution_authority": False,
    }
