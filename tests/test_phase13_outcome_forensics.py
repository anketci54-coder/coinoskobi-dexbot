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


def test_negative_blocked_durable_winner_is_not_missed_opportunity_fallback():
    row = {
        "token": "0xnegative",
        "pool": "0xpool",
        "entry_price": 1.0,
        "max_price": 125.0,
        "signal_state": "NEGATIVE",
        "candidate_action": "BLOCK",
        "observed_at": 2.0,
        "decision_history_id": 13,
        "context_json": "{}",
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[],
        durable_counterfactual_events=[row],
    )

    assert result["missed_opportunities"][
        "sample_count"
    ] == 0


def test_durable_row_wins_without_double_counting_same_decision():
    short = {
        "token": "0xmoon",
        "pool": "0xpool",
        "entry_price": 1.0,
        "realized_return": 1.1,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "observed_at": 1.0,
        "classification": {
            "outcome_class": "MISSED_OPPORTUNITY",
        },
        "context": {
            "reason": "PLAN_BLOCKED",
        },
    }
    durable = {
        "token": "0xmoon",
        "pool": "0xpool",
        "entry_price": 1.0,
        "max_price": 125.0,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "observed_at": 1.0,
        "decision_history_id": 77,
        "context_json": (
            '{"reason":"PLAN_BLOCKED"}'
        ),
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[short],
        durable_counterfactual_events=[durable],
    )

    missed = result["missed_opportunities"]

    assert missed["sample_count"] == 1
    assert missed["multiple_counts"] == {
        "100X_PLUS": 1,
    }
    assert missed["blocker_counts"][
        "PLAN_BLOCKED"
    ] == 1


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
    assert forensic["trade_permission"] is False
    assert forensic["trade_authority"] is False
    assert forensic["decision_authority"] is False
    assert forensic["paper_authority"] is False
    assert forensic["live_authority"] is False
    assert forensic["wallet_authority"] is False
    assert forensic["signing_authority"] is False
    assert forensic["execution_authority"] is False



def test_none_only_lifecycle_snapshot_is_not_evidence():
    row = _paper_event(
        realized_return=-0.05,
    )

    row["lifecycle_snapshot"] = {
        "highest_price": None,
        "lowest_price": None,
        "gross_pnl_usdt": None,
        "net_pnl_usdt": None,
    }

    result = build_outcome_forensics(
        paper_events=[row],
        counterfactual_events=[],
    )

    paper = result["paper"]

    assert (
        paper["lifecycle_evidence_count"]
        == 0
    )

    assert (
        paper["lifecycle_evidence_missing_count"]
        == 1
    )


def test_unidentifiable_missed_rows_use_stable_content_dedupe():
    malformed = {
        "entry_price": 1.0,
        "realized_return": 9.0,
        "signal_state": "POSITIVE",
        "candidate_action": "WATCH",
        "classification": {
            "outcome_class": (
                "MISSED_OPPORTUNITY"
            ),
        },
        "context": {
            "reason": "PLAN_BLOCKED",
        },
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[
            dict(malformed),
            dict(malformed),
        ],
    )

    forensic = (
        result["missed_opportunities"]
    )

    assert forensic["sample_count"] == 1
    assert forensic["multiple_counts"][
        "10X_PLUS"
    ] == 1



def test_malformed_opening_context_does_not_abort_forensics():
    row = _paper_event(
        realized_return=-0.05,
    )
    row["evidence"] = {
        "expected_context": "malformed",
    }

    result = build_outcome_forensics(
        paper_events=[row],
        counterfactual_events=[],
    )

    assert result["paper"]["sample_count"] == 1


def test_expected_loss_positive_block_is_not_missed_opportunity_fallback():
    row = {
        "token": "0xexpectedloss",
        "pool": "0xpool",
        "entry_price": 1.0,
        "max_price": 5.0,
        "signal_state": "POSITIVE",
        "candidate_action": "BLOCK",
        "observed_at": 77.0,
        "classification": {
            "outcome_class": "EXPECTED_LOSS",
        },
        "context": {
            "reason": "PLAN_BLOCKED",
        },
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[row],
    )

    assert result[
        "missed_opportunities"
    ]["sample_count"] == 0


def test_native_currency_cost_drag_is_detected_without_usdt_relabel():
    row = _paper_event(
        realized_return=-0.02,
    )
    row["lifecycle_snapshot"] = {
        "highest_price": None,
        "lowest_price": None,
        "gross_pnl_usdt": None,
        "net_pnl_usdt": None,
        "gross_pnl": 0.02,
        "net_pnl": -0.01,
        "pnl_currency": "BNB",
    }

    result = build_outcome_forensics(
        paper_events=[row],
        counterfactual_events=[],
    )

    paper = result["paper"]

    assert paper["cost_drag_loss_count"] == 1

    example = paper["loss_examples"][0]

    assert example["gross_pnl_usdt"] is None
    assert example["net_pnl_usdt"] is None
    assert example["gross_pnl"] == 0.02
    assert example["net_pnl"] == -0.01
    assert example["pnl_currency"] == "BNB"



def test_post_promotion_multiple_is_not_missed_opportunity():
    observed_at = 1000.0
    promoted_at = 2000.0

    row = {
        "token": "0xpromoted",
        "pool": "0xpool",
        "entry_price": 1.0,
        "max_price": 10.5,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "observed_at": observed_at,
        "promoted_at": promoted_at,
        "first_2x_at": promoted_at + 10.0,
        "first_5x_at": promoted_at + 20.0,
        "first_10x_at": promoted_at + 30.0,
        "decision_history_id": 501,
        "context_json": (
            '{"reason":"PLAN_BLOCKED"}'
        ),
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[],
        durable_counterfactual_events=[row],
    )

    missed = result[
        "missed_opportunities"
    ]

    assert missed["sample_count"] == 0


def test_only_pre_promotion_multiple_is_attributed_as_missed():
    observed_at = 1000.0
    promoted_at = 5000.0

    row = {
        "token": "0xpromoted",
        "pool": "0xpool",
        "entry_price": 1.0,
        "max_price": 10.5,
        "signal_state": "POSITIVE",
        "candidate_action": "DOWNGRADE",
        "observed_at": observed_at,
        "promoted_at": promoted_at,
        "first_2x_at": observed_at + 100.0,
        "first_5x_at": promoted_at + 20.0,
        "first_10x_at": promoted_at + 30.0,
        "decision_history_id": 502,
        "context_json": (
            '{"reason":"PLAN_BLOCKED"}'
        ),
    }

    result = build_outcome_forensics(
        paper_events=[],
        counterfactual_events=[],
        durable_counterfactual_events=[row],
    )

    missed = result[
        "missed_opportunities"
    ]

    assert missed["sample_count"] == 1
    assert missed["multiple_counts"] == {
        "2X_PLUS": 1,
    }

    assert missed["examples"][0][
        "max_multiple"
    ] is None
