from app.strategy.unified_score import UnifiedScoreEngine


def evaluate(
    *,
    prices,
    hard_block=False,
    mev_status="LOW_EXPOSURE",
    reserve_change=0.05,
    latest_reserve_change=None,
):
    return UnifiedScoreEngine().evaluate(
        strategy={
            "decision": "PAPER_BUY",
            "structural_ready": True,
        },
        risk_gate={
            "hard_block": hard_block,
            "sellability": "SELLABLE",
            "honeypot": "NO",
            "local_evidence_complete": True,
            "local_evidence": {
                "exit_feasibility": {
                    "spot_price_series_usd": prices,
                    "quote_reserve_usd": 10000.0,
                    "reserve_change_fraction": reserve_change,
                    "latest_reserve_change_fraction": (
                        latest_reserve_change
                    ),
                }
            },
        },
        trap_risk={
            "evidence": {
                "buy_tax": 0,
                "sell_tax": 0,
            }
        },
        mev_risk={"status": mev_status},
    )


def test_positive_accelerating_continuation_is_hot():
    result = evaluate(prices=[1.0, 1.05, 1.12])
    assert result["opportunity_state"] == "HOT"
    assert result["opportunity_reason"] == "ACTIVE_CONTINUATION_READY"
    assert result["score_authority"] is False
    assert result["opportunity_score"] is None


def test_positive_decelerating_continuation_can_still_be_hot():
    result = evaluate(prices=[1.0, 1.10, 1.15])
    assert result["opportunity_state"] == "HOT"
    assert result["opportunity_reason"] == "ACTIVE_CONTINUATION_READY"


def test_recovery_breakout_can_be_hot_after_one_positive_step():
    result = evaluate(prices=[1.0, 0.90, 1.02])
    assert result["opportunity_state"] == "HOT"
    assert result["opportunity_reason"] == "ACTIVE_RECOVERY_BREAKOUT_READY"
    assert result["opportunity"]["recovery_breakout"] is True


def test_dead_cat_bounce_does_not_become_recovery_breakout():
    result = evaluate(prices=[1.0, 0.90, 0.95])
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "POSITIVE_CONTINUATION_NOT_ESTABLISHED"
    assert result["opportunity"]["recovery_breakout"] is False


def test_recovery_breakout_requires_supporting_latest_flow():
    result = evaluate(
        prices=[1.0, 0.90, 1.02],
        reserve_change=0.10,
        latest_reserve_change=-0.02,
    )
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "QUOTE_FLOW_NOT_SUPPORTING_MOVE"
    assert result["opportunity"]["recovery_breakout"] is False


def test_negative_latest_move_stays_watch_not_reject():
    result = evaluate(prices=[1.0, 1.08, 1.04])
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "ACTIVE_MOMENTUM_NOT_POSITIVE"


def test_single_positive_step_below_prior_range_is_not_enough():
    result = evaluate(prices=[1.0, 0.98, 0.99])
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "POSITIVE_CONTINUATION_NOT_ESTABLISHED"


def test_missing_price_history_stays_watch():
    result = evaluate(prices=[1.0, 1.01])
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "ACTIVE_PRICE_SERIES_NOT_READY"


def test_quote_flow_must_not_oppose_price_move():
    result = evaluate(
        prices=[1.0, 1.05, 1.12],
        reserve_change=0.0,
    )
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "QUOTE_FLOW_NOT_SUPPORTING_MOVE"


def test_latest_quote_outflow_overrides_positive_wide_interval():
    result = evaluate(
        prices=[1.0, 2.0, 2.1],
        reserve_change=0.10,
        latest_reserve_change=-0.08,
    )
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "QUOTE_FLOW_NOT_SUPPORTING_MOVE"
    assert result["opportunity"]["quote_flow_state"] == "OPPOSING"


def test_latest_quote_inflow_can_confirm_after_flat_wide_interval():
    result = evaluate(
        prices=[1.0, 1.05, 1.12],
        reserve_change=0.0,
        latest_reserve_change=0.02,
    )
    assert result["opportunity_state"] == "HOT"
    assert result["opportunity"]["quote_flow_state"] == "SUPPORTING"


def test_missing_quote_flow_does_not_veto_valid_continuation():
    result = evaluate(
        prices=[1.0, 1.05, 1.12],
        reserve_change=None,
        latest_reserve_change=None,
    )
    assert result["opportunity_state"] == "HOT"
    assert result["opportunity_reason"] == "ACTIVE_CONTINUATION_READY"
    assert result["opportunity"]["quote_flow_state"] == "UNKNOWN"


def test_high_execution_exposure_stays_watch():
    result = evaluate(
        prices=[1.0, 1.05, 1.12],
        mev_status="HIGH_EXPOSURE",
    )
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "EXECUTION_EXPOSURE_HIGH"


def test_confirmed_hard_block_rejects():
    result = evaluate(
        prices=[1.0, 1.05, 1.12],
        hard_block=True,
    )
    assert result["opportunity_state"] == "REJECT"
    assert result["hard_block"] is True


def test_coverage_score_is_diagnostic_only():
    result = evaluate(prices=[1.0, 1.05, 1.12])
    assert result["score"] == 100
    assert result["score_meaning"] == "EVIDENCE_COVERAGE_DIAGNOSTIC_ONLY"
    assert result["trade_authority"] is False
