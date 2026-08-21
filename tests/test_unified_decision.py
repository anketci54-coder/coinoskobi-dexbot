from app.strategy.decision import (
    UnifiedDecisionEngine,
)


def decide(**overrides):
    data = {
        "strategy_decision": (
            "PAPER_BUY"
        ),

        "sellability": (
            "UNKNOWN"
        ),

        "local_evidence_complete": (
            False
        ),

        "hard_block": False,
    }

    data.update(
        overrides
    )

    return (
        UnifiedDecisionEngine()
        .evaluate(
            data
        )
    )


def test_hard_block_always_rejects():
    assert (
        decide(
            hard_block=True
        )["decision"]
        == "REJECT"
    )


def test_verified_sellability_is_candidate_without_score_threshold():
    assert (
        decide(
            sellability=(
                "SELLABLE"
            )
        )["decision"]
        == "PAPER_BUY_CANDIDATE"
    )


def test_unknown_with_local_math_evidence_is_candidate():
    assert (
        decide(
            local_evidence_complete=True
        )["decision"]
        == "PAPER_BUY_CANDIDATE"
    )


def test_unknown_without_local_evidence_requires_more_evidence():
    assert (
        decide()[
            "decision"
        ]
        == "REQUIRE_MORE_EVIDENCE"
    )


def test_no_authority():
    result = decide(
        sellability=(
            "SELLABLE"
        )
    )

    assert (
        result[
            "paper_authority"
        ]
        is False
    )

    assert (
        result[
            "live_authority"
        ]
        is False
    )

    assert (
        result[
            "wallet_authority"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        is False
    )
