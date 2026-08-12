PROPOSALS = {
    "KEEP",
    "REVIEW",
    "INCREASE_WEIGHT_PROPOSAL",
    "DECREASE_WEIGHT_PROPOSAL",
    "TIGHTEN_THRESHOLD_PROPOSAL",
    "RELAX_THRESHOLD_PROPOSAL",
    "INSUFFICIENT_EVIDENCE",
}


def build_calibration_proposal(
    calibration,
    target="WEIGHT",
    *,
    min_confidence=0.40,
    false_positive_trigger=0.35,
    false_negative_trigger=0.35,
    hard_safety_target=False,
):
    stats = dict(calibration or {})
    target = (target or "").strip().upper()

    state = stats.get(
        "state",
        "UNKNOWN",
    )

    confidence = _ratio(
        stats.get(
            "confidence",
            0.0,
        )
    )

    fp = _ratio_or_none(
        stats.get(
            "false_positive_ratio"
        )
    )

    fn = _ratio_or_none(
        stats.get(
            "false_negative_ratio"
        )
    )

    minimum_met = bool(
        stats.get(
            "minimum_sample_met",
            False,
        )
    )

    if hard_safety_target:
        proposal = "REVIEW"
        reason = "HARD_SAFETY_WEAKENING_FORBIDDEN"

    elif target not in {
        "WEIGHT",
        "THRESHOLD",
    }:
        proposal = "REVIEW"
        reason = "UNSUPPORTED_TARGET"

    elif (
        state != "CALIBRATION_READY"
        or not minimum_met
    ):
        proposal = "INSUFFICIENT_EVIDENCE"
        reason = "MINIMUM_SAMPLE_NOT_READY"

    elif confidence < float(
        min_confidence
    ):
        proposal = "REVIEW"
        reason = "LOW_CONFIDENCE"

    elif fp is None or fn is None:
        proposal = "REVIEW"
        reason = "INCOMPLETE_CALIBRATION_RATIOS"

    elif (
        fp >= false_positive_trigger
        and fn >= false_negative_trigger
    ):
        proposal = "REVIEW"
        reason = "CONFLICTING_ERROR_PRESSURE"

    elif (
        fp >= false_positive_trigger
    ):
        if target == "WEIGHT":
            proposal = (
                "DECREASE_WEIGHT_PROPOSAL"
            )
        else:
            proposal = (
                "TIGHTEN_THRESHOLD_PROPOSAL"
            )

        reason = "FALSE_POSITIVE_PRESSURE"

    elif (
        fn >= false_negative_trigger
    ):
        if target == "WEIGHT":
            proposal = (
                "INCREASE_WEIGHT_PROPOSAL"
            )
        else:
            proposal = (
                "RELAX_THRESHOLD_PROPOSAL"
            )

        reason = "FALSE_NEGATIVE_PRESSURE"

    else:
        proposal = "KEEP"
        reason = "CALIBRATION_WITHIN_BOUNDS"

    return {
        "proposal": proposal,
        "reason": reason,
        "target": target,
        "confidence": confidence,
        "false_positive_ratio": fp,
        "false_negative_ratio": fn,
        "valid_proposal": (
            proposal in PROPOSALS
        ),
        "proposal_only": True,
        "apply_allowed": False,
        "automatic_apply_allowed": False,
        "config_write_allowed": False,
        "threshold_write_allowed": False,
        "weight_write_allowed": False,
        "strategy_rewrite_allowed": False,
        "source_code_edit_allowed": False,
        "hard_safety_weakening_allowed": False,
        "ai_authority": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _ratio(value):
    try:
        return max(
            0.0,
            min(
                1.0,
                float(value),
            ),
        )
    except (TypeError, ValueError):
        return 0.0


def _ratio_or_none(value):
    if value is None:
        return None

    try:
        return max(
            0.0,
            min(
                1.0,
                float(value),
            ),
        )
    except (TypeError, ValueError):
        return None
