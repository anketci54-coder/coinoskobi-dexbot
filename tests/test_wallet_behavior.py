from app.dex.wallet_behavior import classify_wallet_behavior


def test_accumulation():
    r = classify_wallet_behavior(
        5, 1, 500, 100, 6, 4, 2
    )
    assert "ACCUMULATION_EVIDENCE" in r["behavior_tags"]


def test_distribution():
    r = classify_wallet_behavior(
        1, 5, 100, 500, 6, 4, 2
    )
    assert "DISTRIBUTION_EVIDENCE" in r["behavior_tags"]


def test_burst():
    r = classify_wallet_behavior(
        1, 1, 10, 10, 2, 9, 2
    )
    assert "BURST_ACTIVITY" in r["behavior_tags"]


def test_dormant_to_active():
    r = classify_wallet_behavior(
        1, 0, 10, 0, 1, 1, 0
    )
    assert "DORMANT_TO_ACTIVE" in r["behavior_tags"]


def test_repeated_interaction():
    r = classify_wallet_behavior(
        1, 1, 10, 10, 4, 2, 1
    )
    assert "REPEATED_INTERACTION" in r["behavior_tags"]


def test_neutral():
    r = classify_wallet_behavior(
        1, 1, 10, 10, 1, 1, 1
    )
    assert r["state"] == "NEUTRAL"


def test_stale_unknown():
    r = classify_wallet_behavior(
        5, 0, 500, 0, 10, 10, 0,
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"
    assert r["behavior_tags"] == []


def test_no_identity_or_trade_authority():
    r = classify_wallet_behavior(
        5, 1, 500, 100, 6, 4, 2
    )
    assert r["identity_proof"] is False
    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
