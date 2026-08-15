OUTCOME_CLASSES = (
    "VALID_SIGNAL",
    "FALSE_POSITIVE",
    "FALSE_NEGATIVE",
    "AVOIDED_LOSS",
    "MISSED_OPPORTUNITY",
    "EXIT_FAILURE",
    "EXPECTED_LOSS",
)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_bucket(value):
    score = _number(value)

    if score is None:
        return "UNKNOWN"
    if score >= 95:
        return "95_PLUS"
    if score >= 90:
        return "90_TO_95"
    if score >= 80:
        return "80_TO_90"
    return "BELOW_80"


def build_outcome_segments(
    events,
    *,
    min_samples=20,
    max_segments=128,
):
    rows = list(events)
    segments = {}

    for row in rows:
        outcome = (
            row.get("classification", {})
            .get("outcome_class", "UNKNOWN")
        )

        evidence = row.get("evidence") or {}
        opening = (
            evidence.get("expected_context", {})
            .get("opening_context")
            or row.get("context")
            or {}
        )
        raw = (
            opening.get("raw_signals")
            or opening
        )

        reason = str(
            row.get("close_reason")
            or "UNKNOWN"
        ).upper()

        sellability = str(
            raw.get("sellability_status")
            or raw.get("sellability")
            or "UNKNOWN"
        ).upper()

        score_bucket = _score_bucket(
            raw.get("unified_score")
            if raw.get("unified_score") is not None
            else raw.get("score")
        )

        key = "|".join((
            outcome,
            reason,
            sellability,
            score_bucket,
        ))

        if (
            key not in segments
            and len(segments) >= max(
                1,
                int(max_segments),
            )
        ):
            key = "OVERFLOW"

        segment = segments.setdefault(
            key,
            {
                "outcome_class": outcome,
                "close_reason": reason,
                "sellability": sellability,
                "score_bucket": score_bucket,
                "sample_count": 0,
                "return_sum": 0.0,
                "return_count": 0,
                "exit_drift_sum": 0.0,
                "exit_drift_count": 0,
            },
        )

        segment["sample_count"] += 1

        realized_return = _number(
            row.get("realized_return")
        )

        if realized_return is not None:
            segment["return_sum"] += (
                realized_return
            )
            segment["return_count"] += 1

        drift = _number(
            row.get(
                "exit_price_drift_ratio"
            )
        )

        if drift is not None:
            segment["exit_drift_sum"] += drift
            segment["exit_drift_count"] += 1

    result = {}

    for key, segment in segments.items():
        return_count = segment.pop(
            "return_count"
        )
        return_sum = segment.pop(
            "return_sum"
        )
        drift_count = segment.pop(
            "exit_drift_count"
        )
        drift_sum = segment.pop(
            "exit_drift_sum"
        )

        result[key] = {
            **segment,
            "average_return": (
                return_sum / return_count
                if return_count
                else None
            ),
            "average_exit_drift": (
                drift_sum / drift_count
                if drift_count
                else None
            ),
            "exit_drift_sample_count": (
                drift_count
            ),
        }

    counts = {
        name: sum(
            row["sample_count"]
            for row in result.values()
            if row["outcome_class"] == name
        )
        for name in OUTCOME_CLASSES
    }

    known_samples = sum(counts.values())
    required = max(1, int(min_samples))

    return {
        "state": (
            "READY"
            if known_samples >= required
            else "INSUFFICIENT"
        ),
        "sample_count": known_samples,
        "total_event_count": len(rows),
        "minimum_sample_count": required,
        "minimum_sample_met": (
            known_samples >= required
        ),
        "class_diversity_ready": (
            counts["VALID_SIGNAL"] > 0
            and counts["FALSE_POSITIVE"] > 0
        ),
        "outcome_counts": counts,
        "missing_outcome_families": [
            name
            for name in OUTCOME_CLASSES
            if counts[name] == 0
        ],
        "segments": result,
        "segment_count": len(result),
        "max_segments": max(1, int(max_segments)),
        "bounded": True,
        "raw_db_scan": False,
        "external_fetch": False,
        "provider_call": False,
        "proposal_only": True,
        "automatic_apply_allowed": False,
        "config_write_allowed": False,
        "threshold_write_allowed": False,
        "weight_write_allowed": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
