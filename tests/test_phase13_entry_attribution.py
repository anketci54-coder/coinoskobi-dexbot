import pytest

from app.learning.entry_context import (
    build_entry_signal_attribution,
    build_exit_baseline,
    to_outcome_relative_states,
)
from app.learning.runtime_outcome_feed import (
    RuntimeLearningOutcomeFeed,
)


def test_entry_attribution_is_captured_without_hindsight():
    attribution = (
        build_entry_signal_attribution(
            strategy_decision="PAPER_BUY",
            unified_decision=(
                "PAPER_BUY_CANDIDATE"
            ),
            hard_block=False,
            sellability_status=(
                "SELLABILITY_UNKNOWN"
            ),
        )
    )

    assert attribution == {
        "paper_entry": "POSITIVE",
        "strategy_decision": "POSITIVE",
        "unified_decision": "POSITIVE",
        "risk_gate": "POSITIVE",
        "sellability": "UNKNOWN",
    }


def test_exit_baseline_is_bounded_and_proposal_only():
    baseline = build_exit_baseline(
        entry_price=1.0,
        take_profit_price=1.2,
        stop_loss_price=0.9,
    )

    assert baseline[
        "version"
    ] == "PHASE13A_V1"

    assert baseline[
        "bounded_price_refresh"
    ] is True

    assert baseline[
        "hindsight_reconstructed"
    ] is False

    assert baseline[
        "automatic_apply_allowed"
    ] is False

    assert baseline[
        "execution_authority"
    ] is False


def test_learning_payload_contains_exit_drift():
    feed = RuntimeLearningOutcomeFeed()

    result = feed.observe_paper_close(
        position_id=13,
        token="0xtoken",
        observed_at=(
            "2026-01-01T00:00:00+00:00"
        ),
        evaluated_at=(
            "2026-01-01T00:05:00+00:00"
        ),
        entry_price=1.0,
        exit_price=1.5,
        realized_return=0.5,
        close_reason="TAKE_PROFIT",
        expected_exit_price=1.2,
        opening_context={
            "captured_at_entry": True,
            "signal_attribution": {
                "paper_entry": "POSITIVE",
                "strategy_decision": (
                    "POSITIVE"
                ),
                "unified_decision": (
                    "POSITIVE"
                ),
                "risk_gate": "POSITIVE",
                "sellability": "UNKNOWN",
            },
            "hindsight_reconstructed": False,
        },
    )

    assert result["state"] == "OBSERVED"

    payload = result["payload"]

    assert payload[
        "expected_exit_price"
    ] == pytest.approx(1.2)

    assert payload[
        "exit_price_drift_ratio"
    ] == pytest.approx(0.25)

    assert payload[
        "exit_price_drift_available"
    ] is True

    assert payload[
        "attribution"
    ][
        "known_signal_count"
    ] == 4

    assert payload[
        "automatic_apply_allowed"
    ] is False

    assert payload[
        "execution_authority"
    ] is False

def test_valid_signal_maps_entry_evidence_to_support():
    result = to_outcome_relative_states(
        outcome_class="VALID_SIGNAL",
        entry_signal_states={
            "paper_entry": "POSITIVE",
            "risk_gate": "POSITIVE",
            "sellability": "UNKNOWN",
        },
    )

    assert result == {
        "paper_entry": "SUPPORTS_OUTCOME",
        "risk_gate": "SUPPORTS_OUTCOME",
        "sellability": "UNKNOWN",
    }


def test_false_positive_maps_positive_entry_to_opposition():
    result = to_outcome_relative_states(
        outcome_class="FALSE_POSITIVE",
        entry_signal_states={
            "paper_entry": "POSITIVE",
            "risk_gate": "POSITIVE",
            "sellability": "UNKNOWN",
        },
    )

    assert result == {
        "paper_entry": "OPPOSES_OUTCOME",
        "risk_gate": "OPPOSES_OUTCOME",
        "sellability": "UNKNOWN",
    }
