from app.learning.calibration_statistics import (
    build_calibration_statistics,
)


def test_insufficient_sample():
    r = build_calibration_statistics(
        valid_signal_count=5,
        false_positive_count=2,
        min_samples=20,
    )

    assert r["state"] == "INSUFFICIENT_SAMPLE"
    assert r["minimum_sample_met"] is False


def test_calibration_ready():
    r = build_calibration_statistics(
        valid_signal_count=20,
        false_positive_count=5,
        false_negative_count=3,
        avoided_loss_count=4,
        missed_opportunity_count=2,
        exit_failure_count=1,
        min_samples=20,
    )

    assert r["state"] == "CALIBRATION_READY"
    assert r["minimum_sample_met"] is True


def test_hit_ratio():
    r = build_calibration_statistics(
        valid_signal_count=8,
        false_positive_count=2,
        min_samples=5,
    )

    assert r["hit_ratio"] == 0.8
    assert r["false_positive_ratio"] == 0.2


def test_false_negative_ratio_includes_missed_opportunity():
    r = build_calibration_statistics(
        valid_signal_count=7,
        false_negative_count=2,
        missed_opportunity_count=1,
        min_samples=5,
    )

    assert r["false_negative_ratio"] == 0.3


def test_unknown_not_safe_sample():
    r = build_calibration_statistics(
        valid_signal_count=20,
        unknown_count=100,
        min_samples=20,
    )

    assert r["sample_count"] == 20
    assert r["total_sample_count"] == 120
    assert r["unknown_is_safe_sample"] is False


def test_unknown_does_not_satisfy_minimum():
    r = build_calibration_statistics(
        valid_signal_count=2,
        unknown_count=100,
        min_samples=20,
    )

    assert r["state"] == "INSUFFICIENT_SAMPLE"
    assert r["minimum_sample_met"] is False


def test_stale_unknown():
    r = build_calibration_statistics(
        valid_signal_count=100,
        freshness="STALE",
    )

    assert r["state"] == "UNKNOWN"


def test_zero_coverage_unknown():
    r = build_calibration_statistics(
        valid_signal_count=100,
        evidence_coverage=0,
    )

    assert r["state"] == "UNKNOWN"


def test_confidence_grows_with_samples():
    small = build_calibration_statistics(
        valid_signal_count=20,
        min_samples=20,
    )

    large = build_calibration_statistics(
        valid_signal_count=100,
        min_samples=20,
    )

    assert large["confidence"] > small["confidence"]


def test_coverage_reduces_confidence():
    full = build_calibration_statistics(
        valid_signal_count=100,
        evidence_coverage=1.0,
        min_samples=20,
    )

    partial = build_calibration_statistics(
        valid_signal_count=100,
        evidence_coverage=0.5,
        min_samples=20,
    )

    assert partial["confidence"] < full["confidence"]


def test_single_sample_cannot_calibrate():
    r = build_calibration_statistics(
        valid_signal_count=1,
        min_samples=20,
    )

    assert r["single_sample_can_calibrate"] is False
    assert r["state"] == "INSUFFICIENT_SAMPLE"


def test_authority_and_apply_zero():
    r = build_calibration_statistics(
        valid_signal_count=100,
    )

    assert r["automatic_apply_allowed"] is False
    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
