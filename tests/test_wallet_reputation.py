from app.dex.wallet_reputation import evaluate_wallet_reputation


def test_repeat_offender():
    r = evaluate_wallet_reputation(4, 0.2, 0.2)
    assert "REPEAT_OFFENDER" in r["tags"]


def test_coordination_risk():
    r = evaluate_wallet_reputation(0, 0.9, 0.2)
    assert "COORDINATION_RISK" in r["tags"]


def test_concentration_risk():
    r = evaluate_wallet_reputation(0, 0.2, 0.9)
    assert "CONCENTRATION_RISK" in r["tags"]


def test_high_risk():
    r = evaluate_wallet_reputation(3, 0.9, 0.9)
    assert r["state"] == "HIGH_RISK"


def test_soft_decay():
    fresh = evaluate_wallet_reputation(
        2, 0.7, 0.7, soft_age=0
    )
    old = evaluate_wallet_reputation(
        2, 0.7, 0.7, soft_age=80
    )
    assert old["risk_score"] < fresh["risk_score"]


def test_hard_evidence_no_decay():
    a = evaluate_wallet_reputation(
        0, 0, 0,
        hard_evidence=True,
        soft_age=0,
    )
    b = evaluate_wallet_reputation(
        0, 0, 0,
        hard_evidence=True,
        soft_age=100,
    )
    assert a["state"] == "HARD_RISK_EVIDENCE"
    assert b["state"] == "HARD_RISK_EVIDENCE"
    assert b["hard_evidence_decays"] is False


def test_stale_unknown():
    r = evaluate_wallet_reputation(
        5, 1, 1,
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_wallet_reputation(1, 0.3, 0.3)
    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
