import pytest

from app.learning.runtime_outcome_feed import (
    RuntimeLearningOutcomeFeed,
)


def _context(score):
    return {
        "captured_at_entry": True,
        "entry_context_version": "PHASE13A_V1",
        "hindsight_reconstructed": False,
        "raw_signals": {
            "sellability_status": (
                "SELLABILITY_UNKNOWN"
            ),
            "unified_score": score,
        },
        "signal_attribution": {
            "paper_entry": "POSITIVE",
            "strategy_decision": "POSITIVE",
            "unified_decision": "POSITIVE",
            "risk_gate": "POSITIVE",
            "sellability": "UNKNOWN",
        },
    }


def test_bounded_segmentation_is_readmodel_only():
    feed = RuntimeLearningOutcomeFeed(
        min_samples=2,
    )

    feed.observe_paper_close(
        position_id=1,
        token="0xwin",
        observed_at="2026-01-01T00:00:00+00:00",
        evaluated_at="2026-01-01T00:05:00+00:00",
        entry_price=1.0,
        exit_price=1.25,
        expected_exit_price=1.2,
        realized_return=0.25,
        close_reason="TAKE_PROFIT",
        opening_context=_context(92),
    )

    result = feed.observe_paper_close(
        position_id=2,
        token="0xloss",
        observed_at="2026-01-01T00:10:00+00:00",
        evaluated_at="2026-01-01T00:15:00+00:00",
        entry_price=1.0,
        exit_price=0.85,
        expected_exit_price=0.9,
        realized_return=-0.15,
        close_reason="STOP_LOSS",
        opening_context=_context(96),
    )

    segmentation = result[
        "payload"
    ][
        "calibration"
    ][
        "segmentation"
    ]

    assert segmentation["state"] == "READY"
    assert segmentation["sample_count"] == 2
    assert segmentation[
        "class_diversity_ready"
    ] is True
    assert segmentation["segment_count"] == 2
    assert segmentation["bounded"] is True
    assert segmentation["raw_db_scan"] is False
    assert segmentation["provider_call"] is False
    assert segmentation[
        "automatic_apply_allowed"
    ] is False
    assert segmentation[
        "execution_authority"
    ] is False

    win = segmentation["segments"][
        "VALID_SIGNAL|TAKE_PROFIT|"
        "SELLABILITY_UNKNOWN|90_TO_95"
    ]

    loss = segmentation["segments"][
        "FALSE_POSITIVE|STOP_LOSS|"
        "SELLABILITY_UNKNOWN|95_PLUS"
    ]

    assert win["average_return"] == pytest.approx(0.25)
    assert win["average_exit_drift"] == pytest.approx(
        1.25 / 1.2 - 1
    )
    assert loss["average_return"] == pytest.approx(-0.15)



def test_counterfactual_expected_loss_is_segmented():
    from app.learning.counterfactual_observation import (
        CounterfactualObservationStore,
    )
    from app.learning.outcome_segmentation import (
        build_outcome_segments,
    )

    store = CounterfactualObservationStore(
        horizon_seconds=300,
    )

    store.record(
        token="0xa",
        pool="0xpool",
        entry_price=1.0,
        signal_state="POSITIVE",
        candidate_action="DOWNGRADE",
        observed_at=1000,
        context={
            "score": 92,
            "sellability": "SELLABILITY_UNKNOWN",
        },
    )

    store.observe(
        token="0xa",
        current_price=0.8,
        evaluated_at=1300,
    )

    result = build_outcome_segments(
        store.outcome_snapshot(),
        min_samples=20,
    )

    assert result["outcome_counts"][
        "EXPECTED_LOSS"
    ] == 1
    assert result["sample_count"] == 1
    assert result["minimum_sample_met"] is False
    assert result["bounded"] is True
    assert result["provider_call"] is False
    assert result[
        "automatic_apply_allowed"
    ] is False
