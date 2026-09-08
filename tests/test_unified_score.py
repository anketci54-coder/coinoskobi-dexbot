from app.strategy.unified_score import UnifiedScoreEngine


def evaluate(*, prices, hard_block=False, mev_status="LOW_EXPOSURE"):
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
                    "reserve_change_fraction": 0.05,
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


def test_negative_latest_move_stays_watch_not_reject():
    result = evaluate(prices=[1.0, 1.08, 1.04])
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "ACTIVE_MOMENTUM_NOT_POSITIVE"


def test_positive_but_decelerating_move_stays_watch():
    result = evaluate(prices=[1.0, 1.10, 1.15])
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "ACTIVE_MOMENTUM_DECELERATING"


def test_missing_price_history_stays_watch():
    result = evaluate(prices=[1.0, 1.01])
    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "ACTIVE_PRICE_SERIES_NOT_READY"


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
