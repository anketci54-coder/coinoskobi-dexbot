from app.pipeline.paper_admission import paper_admission_decision


def test_strategy_paper_buy_can_admit_when_unified_is_watch():
    result = paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "WATCH", "reason": "ACTIVE_MOMENTUM_NOT_POSITIVE"},
        {"hard_block": False},
        sellability_status="SELLABILITY_OK",
    )
    assert result == "PAPER_BUY"


def test_unified_reject_still_blocks_paper_buy():
    result = paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "REJECT"},
        {"hard_block": False},
        sellability_status="SELLABILITY_OK",
    )
    assert result == "WATCH"
