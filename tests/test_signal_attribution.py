from app.learning.signal_attribution import attribute_signals


def test_supported_attribution():
    r = attribute_signals(
        "VALID_SIGNAL",
        {
            "market_intelligence": "SUPPORTS_OUTCOME",
            "flow_confirmation": "SUPPORTS_OUTCOME",
            "wallet_behavior": "NEUTRAL",
        },
    )

    assert r["state"] == "SUPPORTED_ATTRIBUTION"
    assert r["support_count"] == 2


def test_conflicting_attribution():
    r = attribute_signals(
        "FALSE_POSITIVE",
        {
            "market_intelligence": "SUPPORTS_OUTCOME",
            "adversary_reputation": "OPPOSES_OUTCOME",
        },
    )

    assert r["state"] == "CONFLICTING_ATTRIBUTION"
    assert r["support_count"] == 1
    assert r["opposition_count"] == 1


def test_opposed_attribution():
    r = attribute_signals(
        "FALSE_NEGATIVE",
        {
            "market_regime": "OPPOSES_OUTCOME",
            "whale_flow": "NEUTRAL",
        },
    )

    assert r["state"] == "OPPOSED_ATTRIBUTION"


def test_unknown_signal_state_preserved():
    r = attribute_signals(
        "VALID_SIGNAL",
        {
            "market_intelligence": "NOT_A_REAL_STATE",
        },
    )

    assert r["state"] == "UNRESOLVED_ATTRIBUTION"
    assert r["unknown_signals"] == [
        "market_intelligence"
    ]


def test_missing_outcome_unknown():
    r = attribute_signals(
        "UNKNOWN",
        {
            "market_intelligence": "SUPPORTS_OUTCOME",
        },
    )

    assert r["state"] == "UNKNOWN"


def test_stale_unknown():
    r = attribute_signals(
        "VALID_SIGNAL",
        {
            "market_intelligence": "SUPPORTS_OUTCOME",
        },
        freshness="STALE",
    )

    assert r["state"] == "UNKNOWN"


def test_incomplete_unknown():
    r = attribute_signals(
        "VALID_SIGNAL",
        {
            "market_intelligence": "SUPPORTS_OUTCOME",
        },
        evidence_complete=False,
    )

    assert r["state"] == "UNKNOWN"


def test_hard_safety_separate():
    r = attribute_signals(
        "AVOIDED_LOSS",
        {
            "market_intelligence": "NEUTRAL",
            "flow_confirmation": "OPPOSES_OUTCOME",
        },
        hard_safety_signals=[
            "HONEYPOT_BLOCK",
            "UNSELLABLE_BLOCK",
        ],
    )

    assert r[
        "hard_safety_separate_from_soft_attribution"
    ] is True

    assert r["hard_safety_signals"] == [
        "HONEYPOT_BLOCK",
        "UNSELLABLE_BLOCK",
    ]


def test_correlation_not_causation():
    r = attribute_signals(
        "VALID_SIGNAL",
        {
            "market_intelligence": "SUPPORTS_OUTCOME",
        },
    )

    assert r["correlation_is_causation"] is False
    assert r["single_signal_owns_outcome"] is False


def test_authority_zero():
    r = attribute_signals(
        "VALID_SIGNAL",
        {
            "market_intelligence": "SUPPORTS_OUTCOME",
        },
    )

    assert r["hindsight_rewrite_allowed"] is False
    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
