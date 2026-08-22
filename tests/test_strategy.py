from app.strategy.engine import (
    StrategyEngine,
)


def test_empty_evidence_has_zero_coverage_and_no_buy():
    data = (
        StrategyEngine()
        .evaluate(
            {},
            {},
            {},
        )["data"]
    )

    assert data["score"] == 0

    assert (
        data[
            "score_meaning"
        ]
        == "EVIDENCE_COVERAGE_PERCENT"
    )

    assert (
        data[
            "score_authority"
        ]
        is False
    )

    assert (
        data["decision"]
        != "PAPER_BUY"
    )


def test_structural_candidate_uses_facts_not_score_threshold():
    data = (
        StrategyEngine()
        .evaluate(
            {
                "name": "Token",
                "symbol": "T",
                "decimals": 18,
            },

            {
                "exists": True,
                "quote_ok": True,
            },

            {
                "owner": False,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        )["data"]
    )

    assert data["score"] == 100

    assert (
        data[
            "structural_ready"
        ]
        is True
    )

    assert (
        data["decision"]
        == "PAPER_BUY"
    )


def test_dangerous_capability_is_fact_not_manual_score_penalty():
    safe = (
        StrategyEngine()
        .evaluate(
            {
                "name": "Token",
                "symbol": "T",
                "decimals": 18,
            },

            {
                "exists": True,
                "quote_ok": True,
            },

            {
                "owner": True,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        )["data"]
    )

    risky = (
        StrategyEngine()
        .evaluate(
            {
                "name": "Token",
                "symbol": "T",
                "decimals": 18,
            },

            {
                "exists": True,
                "quote_ok": True,
            },

            {
                "owner": True,
                "mint": True,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        )["data"]
    )

    assert (
        safe["score"]
        == risky["score"]
    )

    assert (
        "MINT_CAPABILITY"
        in risky[
            "reasons"
        ]
    )
