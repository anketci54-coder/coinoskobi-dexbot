from app.dex.flow_agreement import evaluate_flow_agreement


def test_strong():
    r = evaluate_flow_agreement(
        "BULL", "CONFIRMED", "DIVERSE", "DIVERSE",
        "IMPROVING", "HEALTHY",
    )
    assert r["agreement"] == "STRONG_AGREEMENT"


def test_agreement():
    r = evaluate_flow_agreement(
        "BULL", "PARTIAL_CONFIRMATION", "DIVERSE", "DIVERSE",
        "STABLE", "HEALTHY",
    )
    assert r["agreement"] == "AGREEMENT"


def test_partial():
    r = evaluate_flow_agreement(
        "BULL", "PARTIAL_CONFIRMATION", "DIVERSE", "CONCENTRATED",
        "STABLE", "HEALTHY",
    )
    assert r["agreement"] == "PARTIAL_AGREEMENT"


def test_conflict():
    r = evaluate_flow_agreement(
        "BULL", "CONFLICT", "CONCENTRATED", "SINGLE_ACTOR_SPIKE",
        "CRITICAL", "UNHEALTHY",
    )
    assert r["agreement"] == "CONFLICT"


def test_unknown():
    r = evaluate_flow_agreement(
        "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN",
        "UNKNOWN", "UNKNOWN",
    )
    assert r["agreement"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_flow_agreement(
        "BULL", "CONFIRMED", "DIVERSE", "DIVERSE",
        "STABLE", "HEALTHY",
    )
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
