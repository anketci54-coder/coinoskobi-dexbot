from app.dex.scam_rug_patterns import evaluate_scam_rug_patterns


def test_strong_rug_evidence():
    r = evaluate_scam_rug_patterns(
        repeat_rug_count=2,
        liquidity_removal_count=1,
        confidence=0.95,
    )
    assert r["state"] == "STRONG_SCAM_RUG_EVIDENCE"


def test_candidate():
    r = evaluate_scam_rug_patterns(
        honeypot_associations=1,
        confidence=0.80,
    )
    assert r["state"] == "SCAM_RUG_CANDIDATE"


def test_single_funder_not_proof():
    r = evaluate_scam_rug_patterns(
        suspicious_funder_links=1,
        confidence=1.0,
    )
    assert r["state"] == "SUSPICIOUS_ASSOCIATION"
    assert r["same_funder_is_same_actor"] is False
    assert r["single_association_is_proof"] is False


def test_deployer_association():
    r = evaluate_scam_rug_patterns(
        suspicious_deployer_links=2,
        confidence=0.8,
    )
    assert "SUSPICIOUS_DEPLOYER_ASSOCIATION" in r["evidence_tags"]


def test_repeat_launch():
    r = evaluate_scam_rug_patterns(
        repeat_launch_count=4,
        confidence=0.7,
    )
    assert "REPEAT_LAUNCH_PATTERN" in r["evidence_tags"]


def test_none():
    r = evaluate_scam_rug_patterns()
    assert r["state"] == "NONE"


def test_stale_unknown():
    r = evaluate_scam_rug_patterns(
        repeat_rug_count=10,
        confidence=1.0,
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_scam_rug_patterns(
        repeat_rug_count=2,
        confidence=0.9,
    )
    assert r["identity_proof"] is False
    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
