from app.dex.wash_sybil_intelligence import evaluate_wash_sybil


def test_strong_wash_sybil():
    r = evaluate_wash_sybil(
        wallet_count=20,
        repeated_counterparty_ratio=0.9,
        circular_flow_ratio=0.9,
        coordination_score=0.9,
        independent_wallet_ratio=0.1,
    )
    assert r["state"] == "STRONG_WASH_SYBIL_EVIDENCE"


def test_candidate():
    r = evaluate_wash_sybil(
        wallet_count=10,
        repeated_counterparty_ratio=0.8,
        circular_flow_ratio=0.5,
        coordination_score=0.6,
        independent_wallet_ratio=0.2,
    )
    assert r["state"] == "WASH_SYBIL_CANDIDATE"


def test_real_independent_participation():
    r = evaluate_wash_sybil(
        wallet_count=20,
        repeated_counterparty_ratio=0.1,
        circular_flow_ratio=0.1,
        coordination_score=0.1,
        independent_wallet_ratio=0.9,
    )
    assert r["state"] == "INDEPENDENT_PARTICIPATION"
    assert "INDEPENDENT_MULTI_ACTOR_EVIDENCE" in r["evidence_tags"]


def test_wallet_count_not_proof():
    r = evaluate_wash_sybil(
        wallet_count=100,
        independent_wallet_ratio=0.5,
    )
    assert r["wallet_count_is_participation_proof"] is False


def test_fake_multi_actor_risk():
    r = evaluate_wash_sybil(
        wallet_count=20,
        independent_wallet_ratio=0.1,
    )
    assert "FAKE_MULTI_ACTOR_RISK" in r["evidence_tags"]


def test_circular_flow_tag():
    r = evaluate_wash_sybil(
        circular_flow_ratio=0.9,
    )
    assert "CIRCULAR_FLOW" in r["evidence_tags"]


def test_stale_unknown():
    r = evaluate_wash_sybil(
        wallet_count=50,
        repeated_counterparty_ratio=1.0,
        circular_flow_ratio=1.0,
        coordination_score=1.0,
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_wash_sybil(
        wallet_count=20,
        repeated_counterparty_ratio=0.9,
        circular_flow_ratio=0.9,
        coordination_score=0.9,
    )
    assert r["coordination_is_identity_proof"] is False
    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
