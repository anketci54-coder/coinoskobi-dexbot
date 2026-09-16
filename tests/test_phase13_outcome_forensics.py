from app.learning.outcome_forensics import (
    build_outcome_forensics,
)
from app.learning.unified_outcome_readmodel import (
    build_unified_outcome_readmodel,
)


def _paper_event(
    *,
    outcome="FALSE_POSITIVE",
    realized_return=-0.10,
    highest_price=None,
    peak_net_return=None,
    gross_pnl=None,
    net_pnl=None,
    close_reason="MATHEMATICAL_TREND_FLOOR",
):
    lifecycle = {}

    if highest_price is not None:
        lifecycle["highest_price"] = highest_price
    if peak_net_return is not None:
        lifecycle["peak_net_return"] = peak_net_return
    if gross_pnl is not None:
        lifecycle["gross_pnl_usdt"] = gross_pnl
    if net_pnl is not None:
        lifecycle["net_pnl_usdt"] = net_pnl

    return {
        "position_id": 39,
        "token": "0xtoken",
        "entry_price": 1.0,
        "exit_price": 1.0 + realized_return,
        "realized_return": realized_return,
        "close_reason": close_reason,
        "classification": {
            "outcome_class": outcome,
        },
        "evidence": {
            "state": "EVIDENCE_READY",
            "evidence_coverage": 1.0,
            "expected_context": {
                "opening_context": {
                    "entry_context_version": "PHASE13A_V1",
                    "signal_attribution": {
                        "paper_entry": "POSITIVE",
                        "sellability": "POSITIVE",
                    },
                },
            },
        },
        "lifecycle_snapshot": lifecycle,
    }


def test_paper_loss_without_upside_is_classified():
    result = build_outcome_forensics(
        paper_events=[
            _paper_event(highest_price=0.99),
        ],
        counterfactual_events=[],
    )

    paper = result["paper"]

    assert paper["loss_count"] == 1
    assert paper["no_upside_loss_count"] == 1
    assert paper["cause_counts"][
        "NO_UPSIDE_AFTER_ENTRY"
    ] == 1


def test_price_upside_given_back_is_visible_without_overclaiming_net_profit():
    result = build_outcome_forensics(
        paper_events=[
            _paper_event(
                realized_return=-0.08,
                highest_price=1.20,
            ),
        ],
        counterfactual_events=[],
    )

    paper = result["paper"]

    assert (
        paper["price_above_entry_then_loss_count"]
        == 1
    )
    assert paper[
        "confirmed_profit_giveback_count"
    ] == 0
    assert paper["cause_counts"][
        "PRICE_UPSIDE_GIVEN_BACK"
    ] == 1


def test_peak_net_profit_then_loss_is_confirmed_profit_giveback():
    result = build_outcome_forensics(
        paper_events=[
            _paper_event(
                realized_return=-0.07,
                highest_price=1.25,
                peak_net_return=0.12,
            ),
        ],
        counterfactual_events=[],
    )

    paper = result["paper"]

    assert paper[
        "confirmed_profit_giveback_count"
    ] == 1
    assert paper["cause_counts"][
        "CONFIRMED_PROFIT_GIVEBACK"
    ] == 1


def test_positive_gross_negative_net_is_cost_drag_loss():
    result = build_outcome_forensics(
        paper_events=[
            _paper_event(
                realized_return=-0.02,
                gross_pnl=4.0,
                net_pnl=-2.0,
            ),
        ],
        counterfactual_events=[],
    )

    paper = result["paper"]

    assert paper["cost_drag_loss_count"] == 1
    assert paper["cause_counts"][
        "COST_DRAG_LOSS"
    ] == 1


def test_missed_winner_records_multiple_and_original_blockers():
    missed = {
        "token": "0xmoon",
        "pool": "0xpool",
        "entry_price": 1.0,
        "max_price": 125.0,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "observed_at": 1.0,
        "decision_history_id": 11,
        "context_json": (
            '{"plan_blockers":['
            '"PARTICIPATION_EVIDENCE_UNKNOWN"],'
            '"sizing_blockers":['
            '"NET_EDGE_NOT_POSITIVE"],'
            '"sellability":"SELLABILITY_UNKNOWN"}'
        ),
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[],
        durable_counterfactual_events=[missed],
    )

    forensic = result["missed_opportunities"]

    assert forensic["sample_count"] == 1
    assert forensic["multiple_counts"][
        "100X_PLUS"
    ] == 1
    assert forensic["blocker_counts"][
        "PARTICIPATION_EVIDENCE_UNKNOWN"
    ] == 1
    assert forensic["blocker_counts"][
        "NET_EDGE_NOT_POSITIVE"
    ] == 1
    assert forensic["blocker_counts"][
        "SELLABILITY_UNKNOWN"
    ] == 1


def test_explicit_1000x_marker_has_precedence():
    missed = {
        "token": "0xmoon",
        "pool": "0xpool",
        "entry_price": 1.0,
        "max_price": 20.0,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "observed_at": 1.0,
        "decision_history_id": 12,
        "first_1000x_at": 2.0,
        "context_json": "{}",
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[],
        durable_counterfactual_events=[missed],
    )

    assert result["missed_opportunities"][
        "multiple_counts"
    ]["1000X_PLUS"] == 1


def test_unified_phase13d_exposes_forensics_without_authority():
    paper = _paper_event(
        realized_return=-0.05,
        highest_price=1.10,
    )
    missed = {
        "classification": {
            "outcome_class": "MISSED_OPPORTUNITY",
        },
        "realized_return": 2.0,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "context": {
            "reason": "PLAN_BLOCKED",
        },
    }

    result = build_unified_outcome_readmodel(
        paper_events=[paper],
        counterfactual_events=[missed],
        min_paper_samples=1,
        min_counterfactual_samples=1,
    )

    forensic = result["forensics"]

    assert forensic["phase_owner"] == "13D"
    assert forensic["paper"]["loss_count"] == 1
    assert forensic["missed_opportunities"][
        "sample_count"
    ] == 1
    assert forensic["bounded"] is True
    assert forensic["provider_call"] is False
    assert forensic["automatic_apply_allowed"] is False
    assert forensic["hard_safety_weakening_allowed"] is False
    assert forensic["decision_authority"] is False
    assert forensic["paper_authority"] is False
    assert forensic["live_authority"] is False
    assert forensic["wallet_authority"] is False
    assert forensic["execution_authority"] is False
