from app.learning.outcome_evidence import (
    build_outcome_evidence,
)
from app.learning.outcome_classification import (
    classify_outcome,
)
from app.learning.outcome_memory import (
    OutcomeMemory,
)
from app.learning.calibration_statistics import (
    build_calibration_statistics,
)
from app.learning.calibration_proposal import (
    build_calibration_proposal,
)
from app.learning.outcome_decay import (
    decay_outcome_weight,
)
from app.learning.calibration_readmodel import (
    CalibrationReadModel,
    build_calibration_bucket,
)


def test_insufficient_sample_cannot_calibrate():
    stats = build_calibration_statistics(
        valid_signal_count=5,
        false_positive_count=2,
        false_negative_count=1,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="WEIGHT",
    )

    assert stats["state"] == "INSUFFICIENT_SAMPLE"
    assert (
        proposal["proposal"]
        == "INSUFFICIENT_EVIDENCE"
    )
    assert proposal["apply_allowed"] is False


def test_one_large_win_does_not_override_sample_guard():
    stats = build_calibration_statistics(
        valid_signal_count=1,
        min_samples=20,
    )

    assert stats[
        "single_sample_can_calibrate"
    ] is False

    assert stats[
        "state"
    ] == "INSUFFICIENT_SAMPLE"


def test_one_large_loss_does_not_force_calibration():
    stats = build_calibration_statistics(
        false_positive_count=1,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="THRESHOLD",
    )

    assert (
        proposal["proposal"]
        == "INSUFFICIENT_EVIDENCE"
    )


def test_repeated_false_positives_propose_only():
    stats = build_calibration_statistics(
        valid_signal_count=30,
        false_positive_count=30,
        false_negative_count=2,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="THRESHOLD",
    )

    assert (
        proposal["proposal"]
        == "TIGHTEN_THRESHOLD_PROPOSAL"
    )

    assert proposal[
        "automatic_apply_allowed"
    ] is False


def test_repeated_false_negatives_propose_only():
    stats = build_calibration_statistics(
        valid_signal_count=30,
        false_positive_count=2,
        false_negative_count=30,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="WEIGHT",
    )

    assert (
        proposal["proposal"]
        == "INCREASE_WEIGHT_PROPOSAL"
    )

    assert proposal[
        "weight_write_allowed"
    ] is False


def test_avoided_loss_streak_does_not_create_trade_permission():
    stats = build_calibration_statistics(
        valid_signal_count=20,
        avoided_loss_count=30,
        false_positive_count=1,
        false_negative_count=1,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
    )

    assert proposal[
        "trade_permission"
    ] is False

    assert proposal[
        "decision_authority"
    ] is False


def test_missed_opportunity_streak_does_not_auto_relax():
    stats = build_calibration_statistics(
        valid_signal_count=20,
        missed_opportunity_count=30,
        false_negative_count=30,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="THRESHOLD",
    )

    assert proposal[
        "automatic_apply_allowed"
    ] is False

    assert proposal[
        "threshold_write_allowed"
    ] is False


def test_exit_failure_is_separate_outcome():
    result = classify_outcome(
        "POSITIVE",
        "ALLOW",
        realized_direction="UP",
        exit_failed=True,
    )

    assert (
        result["outcome_class"]
        == "EXIT_FAILURE"
    )


def test_missing_outcome_is_not_rewritten():
    evidence = build_outcome_evidence(
        "bsc",
        "obs-missing",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
        realized_outcome=None,
    )

    assert (
        evidence["state"]
        == "PENDING_OUTCOME"
    )

    assert (
        evidence[
            "missing_outcome_is_success"
        ]
        is False
    )

    assert (
        evidence[
            "missing_outcome_is_failure"
        ]
        is False
    )


def test_duplicate_outcome_not_counted_twice():
    memory = OutcomeMemory(100)

    first = memory.add(
        "bsc:obs-1",
        "FALSE_POSITIVE",
    )

    second = memory.add(
        "bsc:obs-1",
        "FALSE_POSITIVE",
    )

    assert first["state"] == "STORED"
    assert second["state"] == "DUPLICATE"
    assert memory.size == 1


def test_out_of_order_or_stale_evidence_not_promoted():
    evidence = build_outcome_evidence(
        "bsc",
        "obs-stale",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
        realized_outcome={
            "return": 0.10,
        },
        freshness="STALE",
    )

    assert evidence["state"] == "UNKNOWN"


def test_regime_change_reduces_soft_memory():
    same = decay_outcome_weight(
        100,
        hard_evidence=False,
        same_regime=True,
    )

    changed = decay_outcome_weight(
        100,
        hard_evidence=False,
        same_regime=False,
    )

    assert (
        changed["effective_weight"]
        < same["effective_weight"]
    )


def test_hard_evidence_survives_regime_change():
    result = decay_outcome_weight(
        5000,
        hard_evidence=True,
        same_regime=False,
    )

    assert (
        result["effective_weight"]
        == 1.0
    )

    assert (
        result[
            "hard_evidence_preserved"
        ]
        is True
    )


def test_survivorship_bias_unknown_samples_not_successes():
    stats = build_calibration_statistics(
        valid_signal_count=20,
        unknown_count=1000,
        min_samples=20,
    )

    assert stats[
        "sample_count"
    ] == 20

    assert stats[
        "total_sample_count"
    ] == 1020

    assert stats[
        "unknown_is_safe_sample"
    ] is False


def test_extreme_unknown_volume_does_not_inflate_confidence():
    low_unknown = build_calibration_statistics(
        valid_signal_count=20,
        unknown_count=0,
        min_samples=20,
    )

    high_unknown = build_calibration_statistics(
        valid_signal_count=20,
        unknown_count=100000,
        min_samples=20,
    )

    assert (
        high_unknown["confidence"]
        == low_unknown["confidence"]
    )


def test_conflicting_error_pressure_requires_review():
    stats = build_calibration_statistics(
        valid_signal_count=30,
        false_positive_count=30,
        false_negative_count=30,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="WEIGHT",
    )

    assert proposal["proposal"] == "REVIEW"

    assert (
        proposal["reason"]
        == "CONFLICTING_ERROR_PRESSURE"
    )


def test_hard_safety_change_is_forbidden():
    stats = build_calibration_statistics(
        valid_signal_count=30,
        false_negative_count=30,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="THRESHOLD",
        hard_safety_target=True,
    )

    assert proposal["proposal"] == "REVIEW"

    assert (
        proposal[
            "hard_safety_weakening_allowed"
        ]
        is False
    )


def test_learning_readmodel_is_bounded_under_pressure():
    model = CalibrationReadModel(
        max_entries=64
    )

    for i in range(10000):
        model.put(
            f"signal-{i}",
            {
                "calibration_bucket": "STABLE",
            },
        )

    assert model.size == 64


def test_readmodel_stale_is_not_ready():
    model = CalibrationReadModel(10)

    model.put(
        "signal",
        {
            "calibration_bucket": "STABLE",
        },
    )

    assert (
        model.get(
            "signal",
            freshness="STALE",
        )["state"]
        == "STALE"
    )


def test_precomputed_bucket_has_zero_apply_authority():
    stats = build_calibration_statistics(
        valid_signal_count=100,
        false_positive_count=5,
        false_negative_count=5,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats
    )

    bucket = build_calibration_bucket(
        stats,
        proposal,
    )

    assert (
        bucket[
            "automatic_calibration_apply"
        ]
        is False
    )

    assert bucket[
        "decision_authority"
    ] is False

    assert bucket[
        "execution_authority"
    ] is False


def test_attempted_automatic_weight_change_is_impossible():
    stats = build_calibration_statistics(
        valid_signal_count=30,
        false_negative_count=30,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="WEIGHT",
    )

    assert (
        proposal[
            "weight_write_allowed"
        ]
        is False
    )

    assert (
        proposal[
            "source_code_edit_allowed"
        ]
        is False
    )


def test_attempted_automatic_threshold_change_is_impossible():
    stats = build_calibration_statistics(
        valid_signal_count=30,
        false_positive_count=30,
        min_samples=20,
    )

    proposal = build_calibration_proposal(
        stats,
        target="THRESHOLD",
    )

    assert (
        proposal[
            "threshold_write_allowed"
        ]
        is False
    )

    assert (
        proposal[
            "config_write_allowed"
        ]
        is False
    )


def test_memory_remains_bounded_with_repeated_errors():
    memory = OutcomeMemory(
        max_entries=128
    )

    for i in range(10000):
        memory.add(
            f"bsc:{i}",
            (
                "FALSE_POSITIVE"
                if i % 2 == 0
                else "FALSE_NEGATIVE"
            ),
            signal_family="market",
        )

    assert memory.size == 128
    assert memory.dropped == 9872
