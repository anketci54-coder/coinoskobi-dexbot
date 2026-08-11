from app.dex.adversary_reputation import evaluate_adversary_reputation


def test_high_risk_combined_evidence():
    r = evaluate_adversary_reputation(
        mev_state="HIGH_MEV_RISK",
        scam_state="SCAM_RUG_CANDIDATE",
        wash_state="WASH_SYBIL_CANDIDATE",
        pumpdump_state="PUMPDUMP_CANDIDATE",
        repeat_offender_count=4,
    )
    assert r["state"] == "HIGH_RISK"


def test_elevated_risk():
    r = evaluate_adversary_reputation(
        scam_state="SCAM_RUG_CANDIDATE",
        pumpdump_state="PUMPDUMP_CANDIDATE",
        repeat_offender_count=1,
    )
    assert r["state"] in {"ELEVATED_RISK", "WATCH"}


def test_repeat_offender_tag():
    r = evaluate_adversary_reputation(
        repeat_offender_count=5,
    )
    assert "REPEAT_OFFENDER" in r["evidence_tags"]


def test_soft_suspicion_decays():
    fresh = evaluate_adversary_reputation(
        mev_state="ELEVATED_MEV_RISK",
        scam_state="SCAM_RUG_CANDIDATE",
        soft_age=0,
    )
    old = evaluate_adversary_reputation(
        mev_state="ELEVATED_MEV_RISK",
        scam_state="SCAM_RUG_CANDIDATE",
        soft_age=80,
    )
    assert old["risk_score"] < fresh["risk_score"]


def test_hard_evidence_does_not_decay():
    fresh = evaluate_adversary_reputation(
        hard_evidence=True,
        scam_state="STRONG_SCAM_RUG_EVIDENCE",
        soft_age=0,
    )
    old = evaluate_adversary_reputation(
        hard_evidence=True,
        scam_state="STRONG_SCAM_RUG_EVIDENCE",
        soft_age=100,
    )

    assert fresh["state"] == "HARD_ADVERSARY_EVIDENCE"
    assert old["state"] == "HARD_ADVERSARY_EVIDENCE"
    assert old["risk_score"] == fresh["risk_score"]
    assert old["hard_evidence_decays"] is False


def test_conflict_safe_downgrade():
    r = evaluate_adversary_reputation(
        mev_state="ELEVATED_MEV_RISK",
        scam_state="SCAM_RUG_CANDIDATE",
        conflicting_evidence=True,
    )
    assert r["state"] == "UNRESOLVED_CONFLICT"
    assert r["conflict_can_force_safe_downgrade"] is True


def test_hard_evidence_beats_conflict():
    r = evaluate_adversary_reputation(
        hard_evidence=True,
        conflicting_evidence=True,
    )
    assert r["state"] == "HARD_ADVERSARY_EVIDENCE"


def test_stale_unknown():
    r = evaluate_adversary_reputation(
        mev_state="HIGH_MEV_RISK",
        scam_state="STRONG_SCAM_RUG_EVIDENCE",
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_benign_states_low_risk():
    r = evaluate_adversary_reputation(
        mev_state="LOW_OR_UNRESOLVED_MEV_RISK",
        scam_state="NONE",
        wash_state="INDEPENDENT_PARTICIPATION",
        pumpdump_state="NONE",
    )
    assert r["state"] == "LOW_RISK"


def test_sniper_alone_not_high_risk():
    r = evaluate_adversary_reputation(
        pumpdump_state="SNIPER_ACTIVITY",
    )
    assert r["state"] == "WATCH"
    assert r["risk_score"] < 0.40


def test_authority_zero():
    r = evaluate_adversary_reputation(
        scam_state="STRONG_SCAM_RUG_EVIDENCE",
    )

    assert r["trade_permission"] is False
    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
