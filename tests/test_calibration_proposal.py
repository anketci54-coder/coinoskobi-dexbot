from app.learning.calibration_proposal import (
    build_calibration_proposal,
)


def ready(
    fp=0.10,
    fn=0.10,
    confidence=0.80,
):
    return {
        "state": "CALIBRATION_READY",
        "minimum_sample_met": True,
        "confidence": confidence,
        "false_positive_ratio": fp,
        "false_negative_ratio": fn,
    }


def test_keep_when_within_bounds():
    r = build_calibration_proposal(
        ready()
    )

    assert r["proposal"] == "KEEP"


def test_high_fp_decreases_weight():
    r = build_calibration_proposal(
        ready(
            fp=0.50,
            fn=0.10,
        ),
        target="WEIGHT",
    )

    assert (
        r["proposal"]
        == "DECREASE_WEIGHT_PROPOSAL"
    )


def test_high_fn_increases_weight():
    r = build_calibration_proposal(
        ready(
            fp=0.10,
            fn=0.50,
        ),
        target="WEIGHT",
    )

    assert (
        r["proposal"]
        == "INCREASE_WEIGHT_PROPOSAL"
    )


def test_high_fp_tightens_threshold():
    r = build_calibration_proposal(
        ready(
            fp=0.50,
            fn=0.10,
        ),
        target="THRESHOLD",
    )

    assert (
        r["proposal"]
        == "TIGHTEN_THRESHOLD_PROPOSAL"
    )


def test_high_fn_relaxes_threshold():
    r = build_calibration_proposal(
        ready(
            fp=0.10,
            fn=0.50,
        ),
        target="THRESHOLD",
    )

    assert (
        r["proposal"]
        == "RELAX_THRESHOLD_PROPOSAL"
    )


def test_conflicting_pressure_requires_review():
    r = build_calibration_proposal(
        ready(
            fp=0.50,
            fn=0.50,
        )
    )

    assert r["proposal"] == "REVIEW"
    assert (
        r["reason"]
        == "CONFLICTING_ERROR_PRESSURE"
    )


def test_insufficient_sample_never_proposes_change():
    stats = ready()

    stats[
        "state"
    ] = "INSUFFICIENT_SAMPLE"

    stats[
        "minimum_sample_met"
    ] = False

    r = build_calibration_proposal(
        stats
    )

    assert (
        r["proposal"]
        == "INSUFFICIENT_EVIDENCE"
    )


def test_low_confidence_review():
    r = build_calibration_proposal(
        ready(
            confidence=0.20,
        )
    )

    assert r["proposal"] == "REVIEW"
    assert r["reason"] == "LOW_CONFIDENCE"


def test_hard_safety_target_cannot_be_weakened():
    r = build_calibration_proposal(
        ready(
            fn=0.90,
        ),
        target="THRESHOLD",
        hard_safety_target=True,
    )

    assert r["proposal"] == "REVIEW"
    assert (
        r["reason"]
        == "HARD_SAFETY_WEAKENING_FORBIDDEN"
    )

    assert (
        r["hard_safety_weakening_allowed"]
        is False
    )


def test_unknown_target_review():
    r = build_calibration_proposal(
        ready(),
        target="SOURCE_CODE",
    )

    assert r["proposal"] == "REVIEW"
    assert (
        r["reason"]
        == "UNSUPPORTED_TARGET"
    )


def test_missing_ratios_review():
    stats = ready()

    stats[
        "false_positive_ratio"
    ] = None

    r = build_calibration_proposal(
        stats
    )

    assert r["proposal"] == "REVIEW"


def test_proposal_has_zero_apply_authority():
    r = build_calibration_proposal(
        ready(
            fn=0.50,
        )
    )

    assert r["proposal_only"] is True
    assert r["apply_allowed"] is False
    assert (
        r["automatic_apply_allowed"]
        is False
    )
    assert (
        r["config_write_allowed"]
        is False
    )
    assert (
        r["threshold_write_allowed"]
        is False
    )
    assert (
        r["weight_write_allowed"]
        is False
    )
    assert (
        r["strategy_rewrite_allowed"]
        is False
    )
    assert (
        r["source_code_edit_allowed"]
        is False
    )
    assert r["ai_authority"] is False
    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert (
        r["execution_authority"]
        is False
    )
