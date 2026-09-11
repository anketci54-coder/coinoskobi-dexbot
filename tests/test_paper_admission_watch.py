from app.pipeline.paper_admission import paper_admission_decision


def test_safe_paper_buy_admits_while_unified_is_watch():
    result = paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "WATCH"},
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


def test_hard_block_rejects_paper_buy():
    result = paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "WATCH"},
        {"hard_block": True},
        sellability_status="SELLABILITY_OK",
    )
    assert result == "REJECT"


def test_sellability_fail_rejects_paper_buy():
    result = paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "WATCH"},
        {"hard_block": False},
        sellability_status="SELLABILITY_FAIL",
    )
    assert result == "REJECT"
