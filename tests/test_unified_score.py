from app.strategy.unified_score import (
    UnifiedScoreEngine,
)


def test_unified_score_is_evidence_coverage_only():
    result = (
        UnifiedScoreEngine()
        .evaluate(
            strategy={
                "decision": "PAPER_BUY",
                "structural_ready": True,
            },

            risk_gate={
                "hard_block": False,
                "sellability": "UNKNOWN",
                "honeypot": "UNKNOWN",
                "local_evidence_complete": False,
            },

            trap_risk={
                "evidence": {},
            },

            mev_risk={
                "status": "UNKNOWN",
            },
        )
    )

    assert (
        result["score"]
        == 100 / 6
    )

    assert (
        result[
            "opportunity_score"
        ]
        is None
    )

    assert (
        result[
            "score_authority"
        ]
        is False
    )

    assert (
        result[
            "total_penalty"
        ]
        is None
    )


def test_complete_evidence_is_100_without_trade_authority():
    result = (
        UnifiedScoreEngine()
        .evaluate(
            strategy={
                "decision": "PAPER_BUY",
                "structural_ready": True,
            },

            risk_gate={
                "hard_block": False,
                "sellability": "SELLABLE",
                "honeypot": "NO",
                "local_evidence_complete": True,
            },

            trap_risk={
                "evidence": {
                    "buy_tax": 0,
                    "sell_tax": 0,
                },
            },

            mev_risk={
                "status": "LOW_EXPOSURE",
            },
        )
    )

    assert (
        result["score"]
        == 100
    )

    assert (
        result[
            "trade_authority"
        ]
        is False
    )


def test_hard_block_is_separate_from_score():
    result = (
        UnifiedScoreEngine()
        .evaluate(
            strategy={
                "decision": "PAPER_BUY",
                "structural_ready": True,
            },

            risk_gate={
                "hard_block": True,
                "sellability": "UNSELLABLE",
                "honeypot": "YES",
                "local_evidence_complete": True,
            },

            trap_risk={
                "evidence": {
                    "buy_tax": 0,
                    "sell_tax": 0,
                },
            },

            mev_risk={
                "status": "LOW_EXPOSURE",
            },
        )
    )

    assert (
        result["score"]
        == 100
    )

    assert (
        result[
            "hard_block"
        ]
        is True
    )
