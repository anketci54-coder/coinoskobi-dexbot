from app.pipeline.engine import PipelineEngine


def test_unified_decision_can_only_veto_legacy_paper_buy():
    strategy = {"decision": "PAPER_BUY"}
    safe = {"hard_block": False}

    assert PipelineEngine._paper_admission_decision(
        strategy,
        {"decision": "PAPER_BUY_CANDIDATE"},
        safe,
    ) == "PAPER_BUY"

    assert PipelineEngine._paper_admission_decision(
        strategy,
        {"decision": "REQUIRE_MORE_EVIDENCE"},
        safe,
    ) == "REQUIRE_MORE_EVIDENCE"

    assert PipelineEngine._paper_admission_decision(
        strategy,
        {"decision": "WATCH"},
        safe,
    ) == "WATCH"

    assert PipelineEngine._paper_admission_decision(
        strategy,
        {"decision": "REJECT"},
        safe,
    ) == "REJECT"


def test_unified_decision_never_upgrades_legacy_reject():
    assert PipelineEngine._paper_admission_decision(
        {"decision": "REJECT"},
        {"decision": "PAPER_BUY_CANDIDATE"},
        {"hard_block": False},
    ) == "REJECT"


def test_hard_block_dominates_paper_admission():
    assert PipelineEngine._paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "PAPER_BUY_CANDIDATE"},
        {"hard_block": True},
    ) == "REJECT"
