from app.strategy.unified_score import (
    UnifiedScoreEngine,
)


def engine():
    return UnifiedScoreEngine()


def base_strategy(score=90):
    return {
        "score": score,
        "decision": "PAPER_BUY",
    }


def clear_gate():
    return {
        "hard_block": False,
        "sellability": "UNKNOWN",
        "honeypot": "UNKNOWN",
    }


def test_unknown_evidence_does_not_penalize_score():
    result = engine().evaluate(
        strategy=base_strategy(),
        risk_gate=clear_gate(),
        trap_risk={
            "signals": [],
            "evidence": {},
        },
        mev_risk={
            "status": "UNKNOWN",
            "severity": "NONE",
        },
    )

    assert result["tax_penalty"] == 0
    assert result["mev_penalty"] == 0

    assert result["confidence"] == 40

    assert (
        result["decision_authority"]
        is False
    )


def test_strategy_score_is_normalized():
    result = engine().evaluate(
        strategy=base_strategy(105),
        risk_gate=clear_gate(),
        trap_risk={
            "signals": [],
            "evidence": {},
        },
        mev_risk={
            "status": "UNKNOWN",
            "severity": "NONE",
        },
    )

    assert result[
        "opportunity_score"
    ] == 100

    assert result["score"] == 100


def test_contract_control_is_not_double_penalized():
    result = engine().evaluate(
        strategy=base_strategy(),
        risk_gate=clear_gate(),
        trap_risk={
            "signals": [{
                "code": "MINT_CAPABILITY",
                "severity": "MEDIUM",
            }],
            "evidence": {
                "mint": True,
            },
        },
        mev_risk={
            "status": "UNKNOWN",
            "severity": "NONE",
        },
    )

    assert result[
        "tax_penalty"
    ] == 0

    assert result[
        "total_penalty"
    ] == 0


def test_tax_uses_strongest_severity_only():
    result = engine().evaluate(
        strategy=base_strategy(105),
        risk_gate=clear_gate(),
        trap_risk={
            "signals": [
                {
                    "code": "BUY_TAX_NONZERO",
                    "severity": "LOW",
                },
                {
                    "code": "SELL_TAX_HIGH",
                    "severity": "HIGH",
                },
                {
                    "code": "ROUND_TRIP_TAX_HIGH",
                    "severity": "HIGH",
                },
            ],
            "evidence": {
                "buy_tax": 5,
                "sell_tax": 20,
                "round_trip_tax": 25,
            },
        },
        mev_risk={
            "status": "UNKNOWN",
            "severity": "NONE",
        },
    )

    assert result[
        "tax_penalty"
    ] == 8

    # No 8 + 8 + 1 double/triple counting.
    assert result[
        "total_penalty"
    ] == 8


def test_mev_penalty_is_independent_dimension():
    result = engine().evaluate(
        strategy=base_strategy(105),
        risk_gate=clear_gate(),
        trap_risk={
            "signals": [],
            "evidence": {},
        },
        mev_risk={
            "status": "HIGH_EXPOSURE",
            "severity": "HIGH",
        },
    )

    assert result[
        "mev_penalty"
    ] == 8

    assert result["score"] == 92


def test_tax_and_mev_penalties_combine():
    result = engine().evaluate(
        strategy=base_strategy(105),
        risk_gate=clear_gate(),
        trap_risk={
            "signals": [{
                "code": "SELL_TAX_ELEVATED",
                "severity": "MEDIUM",
            }],
            "evidence": {
                "sell_tax": 12,
            },
        },
        mev_risk={
            "status": "HIGH_EXPOSURE",
            "severity": "HIGH",
        },
    )

    assert result[
        "tax_penalty"
    ] == 3

    assert result[
        "mev_penalty"
    ] == 8

    assert result[
        "total_penalty"
    ] == 11

    assert result["score"] == 89


def test_known_evidence_raises_confidence_not_score():
    result = engine().evaluate(
        strategy=base_strategy(),
        risk_gate={
            "hard_block": False,
            "sellability": "SELLABLE",
            "honeypot": "NO",
        },
        trap_risk={
            "signals": [],
            "evidence": {
                "buy_tax": 0,
                "sell_tax": 0,
                "round_trip_tax": 0,
            },
        },
        mev_risk={
            "status": "LOW_EXPOSURE",
            "severity": "NONE",
        },
    )

    assert result[
        "confidence"
    ] == 100

    assert result[
        "coverage"
    ] == {
        "strategy": True,
        "sellability": True,
        "tax": True,
        "mev": True,
    }


def test_hard_block_stays_separate_from_score():
    result = engine().evaluate(
        strategy=base_strategy(105),
        risk_gate={
            "hard_block": True,
            "sellability": "UNSELLABLE",
            "honeypot": "YES",
        },
        trap_risk={
            "signals": [],
            "evidence": {},
        },
        mev_risk={
            "status": "UNKNOWN",
            "severity": "NONE",
        },
    )

    assert result["score"] == 100
    assert result["hard_block"] is True

    # High score can NEVER override this flag.
    assert (
        result["trade_authority"]
        is False
    )
