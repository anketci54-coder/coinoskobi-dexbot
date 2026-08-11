from app.dex.flow_quality import evaluate_flow_quality


def test_multi_actor():
    assert evaluate_flow_quality(
        10, 20, 0.25
    )["flow_quality"] == "MULTI_ACTOR"


def test_single_actor_spike():
    assert evaluate_flow_quality(
        1, 1, 1.0
    )["flow_quality"] == "SINGLE_ACTOR_SPIKE"


def test_whale_dominance():
    assert evaluate_flow_quality(
        8, 20, 0.85
    )["flow_quality"] == "SINGLE_ACTOR_SPIKE"


def test_limited():
    assert evaluate_flow_quality(
        3, 5, 0.60
    )["flow_quality"] == "LIMITED_PARTICIPATION"


def test_weak():
    assert evaluate_flow_quality(
        1, 2, 0.60
    )["flow_quality"] == "WEAK"


def test_unknown():
    assert evaluate_flow_quality(
        None, None, None
    )["flow_quality"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_flow_quality(10, 20, 0.2)
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
