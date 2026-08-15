from app.learning.outcome_segmentation import (
    build_outcome_segments,
)


def _eligible_paper_event(row):
    evidence = row.get("evidence") or {}
    opening = (
        evidence.get("expected_context", {})
        .get("opening_context")
        or {}
    )

    outcome_class = (
        row.get("classification", {})
        .get("outcome_class", "UNKNOWN")
    )

    return (
        opening.get("entry_context_version")
        == "PHASE13A_V1"
        and evidence.get("state")
        == "EVIDENCE_READY"
        and evidence.get(
            "evidence_coverage"
        ) == 1.0
        and outcome_class != "UNKNOWN"
    )


def build_unified_outcome_readmodel(
    *,
    paper_events,
    counterfactual_events,
    min_paper_samples=20,
    min_counterfactual_samples=20,
):
    paper_events = list(paper_events)
    counterfactual_events = list(
        counterfactual_events
    )

    eligible_paper_events = [
        row
        for row in paper_events
        if _eligible_paper_event(row)
    ]

    paper = build_outcome_segments(
        eligible_paper_events,
        min_samples=min_paper_samples,
    )

    counterfactual = build_outcome_segments(
        counterfactual_events,
        min_samples=(
            min_counterfactual_samples
        ),
    )

    classes = set(
        paper["outcome_counts"]
    ) | set(
        counterfactual["outcome_counts"]
    )

    combined_counts = {
        name: (
            paper["outcome_counts"].get(
                name,
                0,
            )
            + counterfactual[
                "outcome_counts"
            ].get(name, 0)
        )
        for name in sorted(classes)
    }

    observed_classes = sorted(
        name
        for name, count
        in combined_counts.items()
        if count > 0
    )

    ready = (
        paper["minimum_sample_met"]
        and counterfactual[
            "minimum_sample_met"
        ]
    )

    return {
        "state": (
            "READY"
            if ready
            else "INSUFFICIENT"
        ),
        "paper": {
            "provenance": "PAPER_CLOSE",
            "observation_type": (
                "REALIZED_POSITION"
            ),
            "segmentation": paper,
        },
        "counterfactual": {
            "provenance": (
                "COUNTERFACTUAL_CACHE_OBSERVATION"
            ),
            "observation_type": (
                "NON_ENTERED_CANDIDATE"
            ),
            "segmentation": counterfactual,
        },
        "paper_sample_count": paper[
            "sample_count"
        ],
        "paper_visible_event_count": len(
            paper_events
        ),
        "paper_eligible_event_count": len(
            eligible_paper_events
        ),
        "paper_excluded_event_count": (
            len(paper_events)
            - len(eligible_paper_events)
        ),
        "paper_eligibility_rule": (
            "PHASE13A_V1_EVIDENCE_READY"
        ),
        "legacy_visible_not_calibrated": True,
        "counterfactual_sample_count": (
            counterfactual["sample_count"]
        ),
        "total_visible_sample_count": (
            paper["sample_count"]
            + counterfactual["sample_count"]
        ),
        "combined_outcome_counts": (
            combined_counts
        ),
        "observed_outcome_classes": (
            observed_classes
        ),
        "class_coverage_count": len(
            observed_classes
        ),
        "paper_minimum_met": paper[
            "minimum_sample_met"
        ],
        "counterfactual_minimum_met": (
            counterfactual[
                "minimum_sample_met"
            ]
        ),
        "channels_kept_separate": True,
        "observation_horizons_mixed": False,
        "combined_counts_are_diagnostic_only": True,
        "proposal_state": (
            "EVIDENCE_READY"
            if ready
            else "INSUFFICIENT_EVIDENCE"
        ),
        "bounded": True,
        "precomputed_only": True,
        "raw_db_scan": False,
        "db_aggregate": False,
        "external_fetch": False,
        "provider_call": False,
        "proposal_only": True,
        "automatic_apply_allowed": False,
        "config_write_allowed": False,
        "threshold_write_allowed": False,
        "weight_write_allowed": False,
        "strategy_rewrite_allowed": False,
        "hard_safety_weakening_allowed": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
