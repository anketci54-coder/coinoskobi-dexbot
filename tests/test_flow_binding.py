from app.dex.flow_binding import bind_flow_context


BASE = {
    "freshness": "FRESH",
    "coverage": 1.0,
    "flow_momentum": 0.4,
    "flow_acceleration": 0.1,
    "participation_quality": "DIVERSE",
    "wallet_concentration": "DIVERSE",
    "liquidity_health": "STABLE",
    "reserve_trend": "STABLE",
    "price_impact_health": "HEALTHY",
}


def test_ready():
    r = bind_flow_context(
        BASE,
        {"market_regime": "TRENDING_BULL"},
        {"agreement": "STRONG_AGREEMENT", "agreement_score": 6},
    )
    assert r["flow_context_ready"] is True


def test_stale():
    s = dict(BASE)
    s["freshness"] = "STALE"

    r = bind_flow_context(
        s,
        {"market_regime": "TRENDING_BULL"},
        {"agreement": "STRONG_AGREEMENT"},
    )
    assert r["flow_context_ready"] is False


def test_unknown_regime():
    r = bind_flow_context(
        BASE,
        {"market_regime": "UNKNOWN"},
        {"agreement": "AGREEMENT"},
    )
    assert r["flow_context_ready"] is False


def test_unknown_agreement():
    r = bind_flow_context(
        BASE,
        {"market_regime": "TRENDING_BULL"},
        {"agreement": "UNKNOWN"},
    )
    assert r["flow_context_ready"] is False


def test_authority_zero():
    r = bind_flow_context(BASE, {}, {})
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
