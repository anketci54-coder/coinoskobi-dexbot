from app.learning.unified_outcome_readmodel import (
    build_unified_outcome_readmodel,
)


def _event(
    outcome,
    realized_return,
    provenance,
):
    return {
        "classification": {
            "outcome_class": outcome,
        },
        "evidence": {
            "state": "EVIDENCE_READY",
            "evidence_coverage": 1.0,
            "expected_context": {
                "opening_context": {
                    "entry_context_version": (
                        "PHASE13A_V1"
                    ),
                },
            },
        },
        "realized_return": realized_return,
        "close_reason": "TAKE_PROFIT",
        "context": {
            "score": 92,
            "sellability": "SELLABILITY_UNKNOWN",
            "provenance": provenance,
        },
    }


def test_channels_remain_separate_and_authority_free():
    result = build_unified_outcome_readmodel(
        paper_events=[
            _event(
                "VALID_SIGNAL",
                0.25,
                "PAPER_CLOSE",
            ),
        ],
        counterfactual_events=[
            _event(
                "MISSED_OPPORTUNITY",
                0.20,
                "COUNTERFACTUAL",
            ),
            _event(
                "EXPECTED_LOSS",
                -0.10,
                "COUNTERFACTUAL",
            ),
        ],
        min_paper_samples=20,
        min_counterfactual_samples=20,
    )

    assert result["state"] == "INSUFFICIENT"
    assert result["paper_sample_count"] == 1
    assert result[
        "counterfactual_sample_count"
    ] == 2
    assert result[
        "total_visible_sample_count"
    ] == 3
    assert result[
        "combined_outcome_counts"
    ]["VALID_SIGNAL"] == 1
    assert result[
        "combined_outcome_counts"
    ]["MISSED_OPPORTUNITY"] == 1
    assert result[
        "combined_outcome_counts"
    ]["EXPECTED_LOSS"] == 1
    assert result[
        "channels_kept_separate"
    ] is True
    assert result[
        "observation_horizons_mixed"
    ] is False
    assert result[
        "combined_counts_are_diagnostic_only"
    ] is True
    assert result["raw_db_scan"] is False
    assert result["provider_call"] is False
    assert result[
        "automatic_apply_allowed"
    ] is False
    assert result[
        "execution_authority"
    ] is False


def test_unified_ready_requires_both_channels():
    paper = [
        _event("VALID_SIGNAL", 0.2, "PAPER")
    ]
    counterfactual = [
        _event(
            "AVOIDED_LOSS",
            -0.2,
            "COUNTERFACTUAL",
        )
    ]

    result = build_unified_outcome_readmodel(
        paper_events=paper,
        counterfactual_events=counterfactual,
        min_paper_samples=1,
        min_counterfactual_samples=1,
    )

    assert result["state"] == "READY"
    assert result["paper_minimum_met"] is True
    assert result[
        "counterfactual_minimum_met"
    ] is True
    assert result["proposal_only"] is True
    assert result["weight_write_allowed"] is False



def test_legacy_paper_is_visible_but_not_calibrated():
    legacy = {
        "classification": {
            "outcome_class": "VALID_SIGNAL",
        },
        "evidence": {
            "state": "EVIDENCE_READY",
            "evidence_coverage": 1.0,
            "expected_context": {
                "opening_context": {},
            },
        },
        "realized_return": 0.50,
    }

    eligible = _event(
        "VALID_SIGNAL",
        0.20,
        "PAPER_CLOSE",
    )

    result = build_unified_outcome_readmodel(
        paper_events=[legacy, eligible],
        counterfactual_events=[],
        min_paper_samples=1,
        min_counterfactual_samples=1,
    )

    assert result[
        "paper_visible_event_count"
    ] == 2
    assert result[
        "paper_eligible_event_count"
    ] == 1
    assert result[
        "paper_excluded_event_count"
    ] == 1
    assert result["paper_sample_count"] == 1
    assert result[
        "legacy_visible_not_calibrated"
    ] is True
    assert result["state"] == "INSUFFICIENT"
