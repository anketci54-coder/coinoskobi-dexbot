from app.strategy.exit_intelligence import evaluate_exit_context
from app.strategy.trend_health import classify_trend_health


def signal(**overrides):
    data = {
        "freshness": "FRESH",
        "coverage": 1.0,
        "flow_momentum": 0.4,
        "flow_acceleration": 0.1,
        "reserve_trend": "STABLE",
        "liquidity_health": "STABLE_OR_UNKNOWN",
        "participation_quality": "DIVERSE",
        "wallet_concentration": "DIVERSE",
        "price_impact_health": "HEALTHY",
    }
    data.update(overrides)
    return data


def trend(sig):
    ctx = evaluate_exit_context(
        position_state={},
        runner_state={},
        signal_bundle=sig,
    )
    return classify_trend_health(ctx)


def test_strong():
    result = trend(signal(
        flow_momentum=0.5,
        flow_acceleration=0.2,
    ))
    assert result["trend_health"] == "STRONG"


def test_healthy_neutral():
    result = trend(signal(
        flow_momentum=0.0,
        flow_acceleration=0.0,
    ))
    assert result["trend_health"] == "HEALTHY"


def test_weakening():
    result = trend(signal(
        flow_momentum=-0.2,
        flow_acceleration=-0.1,
        participation_quality="CONCENTRATED",
    ))
    assert result["trend_health"] == "WEAKENING"


def test_break():
    result = trend(signal(
        reserve_trend="BREAK",
    ))
    assert result["trend_health"] == "BREAK"


def test_unknown_when_stale():
    result = trend(signal(
        freshness="STALE",
    ))
    assert result["trend_health"] == "UNKNOWN"


def test_authority_zero():
    result = trend(signal())

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
