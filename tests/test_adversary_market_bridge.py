from app.dex.adversary_market_bridge import bind_adversary_market_context


WALLET_READY = {
    "wallet_context_ready": True,
    "market_context_allowed": True,
    "wallet_id": "bsc:0xabc",
    "wallet_hard_risk": False,
}


def test_low_risk_context_ready():
    r = bind_adversary_market_context(
        WALLET_READY,
        {
            "state": "LOW_RISK",
            "risk_score": 0.0,
            "hard_evidence": False,
            "evidence_tags": [],
        },
    )
    assert r["state"] == "CONTEXT_READY"
    assert r["candidate_action"] == "NO_ADVERSARY_BLOCK"


def test_hard_adversary_blocks_candidate():
    r = bind_adversary_market_context(
        WALLET_READY,
        {
            "state": "HARD_ADVERSARY_EVIDENCE",
            "risk_score": 0.9,
            "hard_evidence": True,
            "evidence_tags": ["STRONG_SCAM_RUG_EVIDENCE"],
        },
    )
    assert r["state"] == "HARD_ADVERSARY_RISK"
    assert r["candidate_action"] == "BLOCK_CANDIDATE"
    assert r["adversary_hard_risk"] is True


def test_high_risk_downgrades():
    r = bind_adversary_market_context(
        WALLET_READY,
        {
            "state": "HIGH_RISK",
            "risk_score": 0.8,
            "hard_evidence": False,
        },
    )
    assert r["candidate_action"] == "DOWNGRADE_CANDIDATE"


def test_elevated_risk_downgrades():
    r = bind_adversary_market_context(
        WALLET_READY,
        {
            "state": "ELEVATED_RISK",
            "risk_score": 0.5,
            "hard_evidence": False,
        },
    )
    assert r["candidate_action"] == "DOWNGRADE_CANDIDATE"


def test_unknown_safe_downgrade():
    r = bind_adversary_market_context(
        WALLET_READY,
        {"state": "UNKNOWN"},
    )
    assert r["state"] == "UNRESOLVED"
    assert r["candidate_action"] == "SAFE_DOWNGRADE"


def test_conflict_safe_downgrade():
    r = bind_adversary_market_context(
        WALLET_READY,
        {"state": "UNRESOLVED_CONFLICT"},
    )
    assert r["candidate_action"] == "SAFE_DOWNGRADE"


def test_wallet_not_ready_safe_downgrade():
    wallet = dict(WALLET_READY)
    wallet["wallet_context_ready"] = False

    r = bind_adversary_market_context(
        wallet,
        {"state": "LOW_RISK"},
    )
    assert r["state"] == "WALLET_CONTEXT_NOT_READY"
    assert r["candidate_action"] == "SAFE_DOWNGRADE"


def test_never_upgrades_candidate():
    r = bind_adversary_market_context(
        WALLET_READY,
        {"state": "LOW_RISK"},
    )
    assert r["can_upgrade_candidate"] is False


def test_hard_safety_never_overridden():
    r = bind_adversary_market_context(
        WALLET_READY,
        {
            "state": "HARD_ADVERSARY_EVIDENCE",
            "hard_evidence": True,
        },
    )
    assert r["hard_safety_override_allowed"] is False


def test_authority_zero():
    r = bind_adversary_market_context(
        WALLET_READY,
        {"state": "LOW_RISK"},
    )

    assert r["trade_permission"] is False
    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
