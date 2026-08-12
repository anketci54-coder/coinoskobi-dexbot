from app.learning.outcome_classification import classify_outcome


def test_valid_signal():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_direction="UP",
    )
    assert r["outcome_class"] == "VALID_SIGNAL"


def test_false_positive():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_direction="DOWN",
    )
    assert r["outcome_class"] == "FALSE_POSITIVE"


def test_avoided_loss():
    r = classify_outcome(
        "NEGATIVE",
        "BLOCK_CANDIDATE",
        realized_direction="DOWN",
    )
    assert r["outcome_class"] == "AVOIDED_LOSS"


def test_false_negative():
    r = classify_outcome(
        "NEGATIVE",
        "BLOCK_CANDIDATE",
        realized_direction="UP",
    )
    assert r["outcome_class"] == "FALSE_NEGATIVE"


def test_missed_opportunity():
    r = classify_outcome(
        "POSITIVE",
        "SAFE_DOWNGRADE",
        realized_direction="UP",
    )
    assert r["outcome_class"] == "MISSED_OPPORTUNITY"


def test_expected_loss():
    r = classify_outcome(
        "POSITIVE",
        "BLOCK_CANDIDATE",
        realized_direction="DOWN",
    )
    assert r["outcome_class"] == "EXPECTED_LOSS"


def test_exit_failure_dominates():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_direction="UP",
        exit_failed=True,
    )
    assert r["outcome_class"] == "EXIT_FAILURE"


def test_return_can_supply_outcome():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_return=0.05,
    )
    assert r["outcome_class"] == "VALID_SIGNAL"


def test_incomplete_unknown():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_direction="UP",
        evidence_complete=False,
    )
    assert r["outcome_class"] == "UNKNOWN"


def test_stale_unknown():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_direction="UP",
        freshness="STALE",
    )
    assert r["outcome_class"] == "UNKNOWN"


def test_missing_realized_outcome_unknown():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
    )
    assert r["outcome_class"] == "UNKNOWN"


def test_hindsight_and_authority_zero():
    r = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_direction="UP",
    )

    assert r["hindsight_rewrite_allowed"] is False
    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
