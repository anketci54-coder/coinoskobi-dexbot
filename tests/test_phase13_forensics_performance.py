from time import perf_counter

from app.learning.outcome_forensics import (
    build_outcome_forensics,
)


def _paper_event(index):
    return {
        "position_id": index,
        "token": f"0x{index:040x}",
        "entry_price": 1.0,
        "exit_price": 0.95,
        "realized_return": -0.05,
        "close_reason": "MATHEMATICAL_TREND_FLOOR",
        "classification": {
            "outcome_class": "FALSE_POSITIVE",
        },
        "evidence": {
            "expected_context": {
                "opening_context": {
                    "signal_attribution": {
                        "paper_entry": "POSITIVE",
                    },
                },
            },
        },
        "lifecycle_snapshot": {
            "highest_price": 1.05,
        },
    }


def _counterfactual_event(index):
    return {
        "token": f"0x{index + 100000:040x}",
        "pool": f"0x{index + 200000:040x}",
        "entry_price": 1.0,
        "realized_return": 1.2,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "observed_at": float(index),
        "decision_history_id": index,
        "classification": {
            "outcome_class": "MISSED_OPPORTUNITY",
        },
        "context": {
            "reason": "PLAN_BLOCKED",
            "plan_blockers": [
                "PARTICIPATION_EVIDENCE_UNKNOWN",
            ],
        },
    }


def test_phase13d_forensics_stays_bounded_and_fast():
    paper = [_paper_event(i) for i in range(10000)]
    counterfactual = [
        _counterfactual_event(i)
        for i in range(10000)
    ]

    started = perf_counter()
    result = build_outcome_forensics(
        paper_events=paper,
        counterfactual_events=counterfactual,
        max_examples=20,
    )
    elapsed = perf_counter() - started

    assert result["paper"]["sample_count"] == 10000
    assert result["missed_opportunities"][
        "sample_count"
    ] == 10000
    assert len(result["paper"]["loss_examples"]) <= 20
    assert len(result["missed_opportunities"]["examples"]) <= 20
    assert result["bounded"] is True
    assert elapsed < 5.0
