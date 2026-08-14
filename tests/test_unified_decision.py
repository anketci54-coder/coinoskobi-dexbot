from app.strategy.decision import (
    UnifiedDecisionEngine,
)


def evaluate(
    score,
    confidence,
    *,
    hard_block=False,
):
    return UnifiedDecisionEngine().evaluate({
        "score": score,
        "confidence": confidence,
        "hard_block": hard_block,
    })


def test_hard_block_always_rejects():
    result = evaluate(
        100,
        100,
        hard_block=True,
    )

    assert (
        result["decision"]
        == "REJECT"
    )

    assert "HARD_BLOCK" in (
        result["reasons"]
    )


def test_high_score_high_confidence_is_paper_candidate():
    result = evaluate(
        90,
        80,
    )

    assert (
        result["decision"]
        == "PAPER_BUY_CANDIDATE"
    )


def test_high_score_low_confidence_requires_evidence():
    result = evaluate(
        95,
        40,
    )

    assert (
        result["decision"]
        == "REQUIRE_MORE_EVIDENCE"
    )


def test_watch_boundary():
    result = evaluate(
        70,
        100,
    )

    assert (
        result["decision"]
        == "WATCH"
    )


def test_below_watch_rejects():
    result = evaluate(
        69.99,
        100,
    )

    assert (
        result["decision"]
        == "REJECT"
    )


def test_score_just_below_paper_is_watch():
    result = evaluate(
        89.99,
        100,
    )

    assert (
        result["decision"]
        == "WATCH"
    )


def test_confidence_boundary():
    below = evaluate(
        95,
        59.99,
    )

    exact = evaluate(
        95,
        60,
    )

    assert (
        below["decision"]
        == "REQUIRE_MORE_EVIDENCE"
    )

    assert (
        exact["decision"]
        == "PAPER_BUY_CANDIDATE"
    )


def test_no_execution_authority():
    result = evaluate(
        100,
        100,
    )

    assert (
        result["decision_authority"]
        is False
    )

    assert (
        result["paper_authority"]
        is False
    )

    assert (
        result["live_authority"]
        is False
    )

    assert (
        result["wallet_authority"]
        is False
    )

    assert (
        result["execution_authority"]
        is False
    )
