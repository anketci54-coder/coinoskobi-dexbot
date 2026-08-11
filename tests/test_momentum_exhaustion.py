from app.strategy.momentum_exhaustion import evaluate_exhaustion


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
    assert evaluate_exhaustion(0.3, sig())["exhaustion_state"] == "NONE"


def test_early():
    r = evaluate_exhaustion(
        0.3,
        sig(flow_acceleration=-0.1),
    )
    assert r["exhaustion_state"] == "EARLY"


def test_confirmed():
    r = evaluate_exhaustion(
        0.3,
        sig(
            flow_momentum=-0.1,
            flow_acceleration=-0.2,
        ),
    )
    assert r["exhaustion_state"] == "CONFIRMED"


def test_price_not_rising():
    r = evaluate_exhaustion(
        -0.2,
        sig(flow_momentum=-0.4),
    )
    assert r["exhaustion_state"] == "NONE"


def test_unknown():
    assert evaluate_exhaustion(
        0.3,
        sig(freshness="STALE"),
    )["exhaustion_state"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_exhaustion(0.3, sig())
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
