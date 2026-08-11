from app.dex.mev_sandwich import (
    evaluate_sandwich_evidence,
    classify_mev_context,
)


def test_strong_sandwich():
    r = evaluate_sandwich_evidence(
        True, True, True, 0.03,
        repeated_pattern_count=3,
        gas_priority_relation=True,
    )
    assert r["state"] == "SANDWICH_STRONG_EVIDENCE"


def test_candidate():
    r = evaluate_sandwich_evidence(
        True, True, True, 0.02,
        repeated_pattern_count=0,
    )
    assert r["state"] == "SANDWICH_CANDIDATE"


def test_ordering_alone_not_proof():
    r = evaluate_sandwich_evidence(
        True, True, True, 0.0,
        repeated_pattern_count=0,
    )
    assert r["state"] == "MEV_LIKE_ORDERING"
    assert r["single_event_is_proof"] is False


def test_partial_evidence():
    r = evaluate_sandwich_evidence(
        True, True, False, 0.01,
    )
    assert r["state"] == "INSUFFICIENT_EVIDENCE"


def test_no_evidence():
    r = evaluate_sandwich_evidence(
        False, False, False, 0,
    )
    assert r["state"] == "NONE"


def test_stale_unknown():
    r = evaluate_sandwich_evidence(
        True, True, True, 0.1,
        repeated_pattern_count=10,
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_normal_arbitrage_not_auto_sandwich():
    r = classify_mev_context(
        "MEV_LIKE_ORDERING",
        arbitrage_like=True,
    )
    assert r["state"] == "NORMAL_ARBITRAGE_POSSIBLE"
    assert r["normal_arbitrage_is_sandwich"] is False


def test_strong_mev_risk():
    r = classify_mev_context(
        "SANDWICH_STRONG_EVIDENCE"
    )
    assert r["state"] == "HIGH_MEV_RISK"


def test_candidate_mev_risk():
    r = classify_mev_context(
        "SANDWICH_CANDIDATE"
    )
    assert r["state"] == "ELEVATED_MEV_RISK"


def test_authority_zero():
    r = evaluate_sandwich_evidence(
        True, True, True, 0.05,
        repeated_pattern_count=3,
    )
    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
