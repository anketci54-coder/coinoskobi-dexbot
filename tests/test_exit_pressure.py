from app.strategy.exit_pressure import evaluate_exit_pressure


def sig(**x):
    s = {
        "freshness": "FRESH",
        "coverage": 1.0,
        "flow_momentum": 0.4,
        "flow_acceleration": 0.1,
        "participation_quality": "DIVERSE",
        "liquidity_health": "STABLE_OR_UNKNOWN",
    }
    s.update(x)
    return s


def test_none():
    assert evaluate_exit_pressure(0.3, sig())["exit_pressure"] == "NONE"


def test_flow_divergence():
    r = evaluate_exit_pressure(0.3, sig(flow_momentum=-0.1))
    assert "PRICE_FLOW_DIVERGENCE" in r["reasons"]


def test_liquidity_divergence():
    r = evaluate_exit_pressure(
        0.3,
        sig(liquidity_health="DETERIORATING"),
    )
    assert "PRICE_LIQUIDITY_DIVERGENCE" in r["reasons"]


def test_high():
    r = evaluate_exit_pressure(
        0.3,
        sig(
            flow_momentum=-0.2,
            flow_acceleration=-0.2,
            participation_quality="CONCENTRATED",
        ),
        "CONFIRMED",
    )
    assert r["exit_pressure"] == "HIGH"


def test_unknown():
    assert evaluate_exit_pressure(
        0.3,
        sig(freshness="STALE"),
    )["exit_pressure"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_exit_pressure(0.3, sig())
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
