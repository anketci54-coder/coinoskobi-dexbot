import pytest


def test_close_position_is_idempotent_contract():
    from app.paper.database import PaperDatabase
    assert callable(PaperDatabase.close_position)
    assert callable(PaperDatabase.closed_positions)


def test_learning_replay_contract_exists():
    from app.paper.manager import PaperManager
    assert callable(PaperManager.replay_closed_outcomes)


def test_unified_admission_helper_contract():
    from app.pipeline.paper_admission import paper_admission_decision

    safe = {"hard_block": False}
    assert paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "PAPER_BUY_CANDIDATE"},
        safe,
    ) == "PAPER_BUY"
    assert paper_admission_decision(
        {"decision": "REJECT"},
        {"decision": "PAPER_BUY_CANDIDATE"},
        safe,
    ) == "REJECT"
    assert paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "PAPER_BUY_CANDIDATE"},
        {"hard_block": True},
    ) == "REJECT"
