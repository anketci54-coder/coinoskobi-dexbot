DEFAULT_MIN_SAMPLES = 20


def build_calibration_statistics(
    valid_signal_count=0,
    false_positive_count=0,
    false_negative_count=0,
    avoided_loss_count=0,
    missed_opportunity_count=0,
    exit_failure_count=0,
    unknown_count=0,
    evidence_coverage=1.0,
    freshness="FRESH",
    min_samples=DEFAULT_MIN_SAMPLES,
):
    valid = _count(valid_signal_count)
    fp = _count(false_positive_count)
    fn = _count(false_negative_count)
    avoided = _count(avoided_loss_count)
    missed = _count(missed_opportunity_count)
    exit_fail = _count(exit_failure_count)
    unknown = _count(unknown_count)

    coverage = _ratio(evidence_coverage)
    minimum = max(1, _count(min_samples))

    known_samples = (
        valid
        + fp
        + fn
        + avoided
        + missed
        + exit_fail
    )

    total_samples = known_samples + unknown

    if freshness != "FRESH":
        state = "UNKNOWN"
    elif known_samples < minimum:
        state = "INSUFFICIENT_SAMPLE"
    elif coverage <= 0:
        state = "UNKNOWN"
    else:
        state = "CALIBRATION_READY"

    hit_denominator = valid + fp
    opportunity_denominator = valid + fn + missed
    risk_denominator = avoided + fp + exit_fail

    hit_ratio = _safe_ratio(valid, hit_denominator)
    false_positive_ratio = _safe_ratio(fp, hit_denominator)
    false_negative_ratio = _safe_ratio(
        fn + missed,
        opportunity_denominator,
    )
    avoided_loss_ratio = _safe_ratio(
        avoided,
        risk_denominator,
    )
    missed_opportunity_ratio = _safe_ratio(
        missed,
        opportunity_denominator,
    )
    exit_failure_ratio = _safe_ratio(
        exit_fail,
        known_samples,
    )

    sample_confidence = min(
        1.0,
        known_samples / float(minimum * 5),
    )

    confidence = round(
        sample_confidence * coverage,
        6,
    )

    return {
        "state": state,
        "sample_count": known_samples,
        "total_sample_count": total_samples,
        "unknown_count": unknown,
        "minimum_sample_count": minimum,
        "minimum_sample_met": known_samples >= minimum,
        "valid_signal_count": valid,
        "false_positive_count": fp,
        "false_negative_count": fn,
        "avoided_loss_count": avoided,
        "missed_opportunity_count": missed,
        "exit_failure_count": exit_fail,
        "hit_ratio": hit_ratio,
        "false_positive_ratio": false_positive_ratio,
        "false_negative_ratio": false_negative_ratio,
        "avoided_loss_ratio": avoided_loss_ratio,
        "missed_opportunity_ratio": missed_opportunity_ratio,
        "exit_failure_ratio": exit_failure_ratio,
        "evidence_coverage": coverage,
        "confidence": confidence,
        "freshness": freshness,
        "unknown_is_safe_sample": False,
        "single_sample_can_calibrate": False,
        "automatic_apply_allowed": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _count(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _ratio(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _safe_ratio(numerator, denominator):
    if denominator <= 0:
        return None

    return round(
        numerator / float(denominator),
        6,
    )
