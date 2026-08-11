from app.dex.adversary_evidence import adversary_evidence


def test_strong():
    r = adversary_evidence(
        "bsc", "0xabc", "sandwich", 4, 0.95
    )
    assert r["state"] == "STRONG_EVIDENCE"


def test_possible():
    r = adversary_evidence(
        "bsc", "0xabc", "wash_trade", 2, 0.70
    )
    assert r["state"] == "POSSIBLE_EVIDENCE"


def test_weak():
    r = adversary_evidence(
        "bsc", "0xabc", "sybil", 1, 0.20
    )
    assert r["state"] == "WEAK_EVIDENCE"


def test_unsupported():
    assert adversary_evidence(
        "bsc", "0xabc", "sandwich", 0, 1
    )["state"] == "UNSUPPORTED"


def test_stale_unknown():
    assert adversary_evidence(
        "bsc", "0xabc", "sandwich", 10, 1,
        freshness="STALE",
    )["state"] == "UNKNOWN"


def test_chain_aware_actor():
    a = adversary_evidence(
        "bsc", "0xabc", "sandwich", 1, .5
    )
    b = adversary_evidence(
        "eth", "0xabc", "sandwich", 1, .5
    )
    assert a["actor_key"] != b["actor_key"]


def test_suspicion_not_proof():
    r = adversary_evidence(
        "bsc", "0xabc", "sandwich", 10, 1
    )
    assert r["suspicion_is_proof"] is False
    assert r["identity_proof"] is False
    assert r["trade_permission"] is False


def test_authority_zero():
    r = adversary_evidence(
        "bsc", "0xabc", "sandwich", 4, .9
    )
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
