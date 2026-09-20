import app.risk.exit_feasibility as exit_module
from app.strategy.unified_score import UnifiedScoreEngine


TOKEN = "0x1111111111111111111111111111111111111111"
PAIR = "0x2222222222222222222222222222222222222222"


def _reset_runtime_history():
    exit_module._RUNTIME_PAIR_PRICE_HISTORY.clear()
    exit_module._RUNTIME_PAIR_PRICE_LAST_BLOCK.clear()


def _risk_gate(*, runtime_prices, latest_flow=0.01):
    return {
        "hard_block": False,
        "sellability": "SELLABLE",
        "honeypot": "NO",
        "local_evidence_complete": True,
        "local_evidence": {
            "exit_feasibility": {
                "pair": PAIR,
                # Deliberately stale/negative block-offset series.
                "spot_price_series_usd": [1.0, 1.10, 1.05],
                "runtime_spot_price_series_usd": list(runtime_prices),
                "quote_reserve_usd": 10000.0,
                "reserve_change_fraction": 0.02,
                "latest_reserve_change_fraction": latest_flow,
            },
        },
    }


def _evaluate(*, runtime_prices, latest_flow=0.01):
    return UnifiedScoreEngine().evaluate(
        strategy={
            "decision": "PAPER_BUY",
            "structural_ready": True,
        },
        risk_gate=_risk_gate(
            runtime_prices=runtime_prices,
            latest_flow=latest_flow,
        ),
        trap_risk={"evidence": {}},
        mev_risk={"status": "LOW_EXPOSURE"},
    )


def test_pair_runtime_history_seeds_once_then_appends_latest_cycle_price():
    _reset_runtime_history()

    first = exit_module._runtime_pair_price_series(
        TOKEN,
        PAIR,
        [1.0, 0.9, 1.0],
    )
    second = exit_module._runtime_pair_price_series(
        TOKEN,
        PAIR,
        [1.0, 0.9, 1.1],
    )
    third = exit_module._runtime_pair_price_series(
        TOKEN,
        PAIR,
        [1.0, 0.9, 1.2],
    )

    assert first == [1.0]
    assert second == [1.0, 1.1]
    assert third == [1.0, 1.1, 1.2]


def test_same_block_is_not_double_counted_but_next_block_is_observed():
    _reset_runtime_history()

    first = exit_module._runtime_pair_price_series(
        TOKEN,
        PAIR,
        [1.0, 0.9, 1.0],
        observation_block=100,
    )
    duplicate = exit_module._runtime_pair_price_series(
        TOKEN,
        PAIR,
        [1.0, 0.9, 1.1],
        observation_block=100,
    )
    next_block = exit_module._runtime_pair_price_series(
        TOKEN,
        PAIR,
        [1.0, 0.9, 1.1],
        observation_block=101,
    )

    assert first == [1.0]
    assert duplicate == first
    assert next_block == [1.0, 1.1]


def test_runtime_pair_history_overrides_stale_block_momentum_for_opportunity():
    result = _evaluate(
        runtime_prices=[1.0, 1.01, 1.02],
    )

    assert result["opportunity_state"] == "HOT"
    assert result["opportunity_reason"] == "ACTIVE_CONTINUATION_READY"
    assert result["opportunity"]["price_series_source"] == "PAIR_RUNTIME_ONCHAIN"
    assert result["opportunity"]["latest_log_return"] > 0


def test_runtime_positive_momentum_cannot_bypass_opposing_quote_flow():
    result = _evaluate(
        runtime_prices=[1.0, 1.01, 1.02],
        latest_flow=-0.01,
    )

    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "QUOTE_FLOW_NOT_SUPPORTING_MOVE"
    assert result["opportunity"]["price_series_source"] == "PAIR_RUNTIME_ONCHAIN"
    assert result["opportunity"]["quote_flow_state"] == "OPPOSING"


def test_zero_quote_flow_is_neutral_not_opposing():
    result = _evaluate(
        runtime_prices=[1.0, 1.01, 1.02],
        latest_flow=0.0,
    )

    assert result["opportunity_state"] == "HOT"
    assert result["opportunity_reason"] == "ACTIVE_CONTINUATION_READY"
    assert result["opportunity"]["quote_flow_state"] == "NEUTRAL"


def test_zero_quote_flow_cannot_enable_recovery_breakout():
    result = _evaluate(
        runtime_prices=[1.0, 0.9, 1.1],
        latest_flow=0.0,
    )

    assert result["opportunity_state"] == "WATCH"
    assert (
        result["opportunity_reason"]
        == "POSITIVE_CONTINUATION_NOT_ESTABLISHED"
    )
    assert result["opportunity"]["recovery_breakout"] is False
    assert result["opportunity"]["quote_flow_state"] == "NEUTRAL"


def test_block_history_remains_fallback_when_runtime_series_is_absent():
    result = _evaluate(
        runtime_prices=[],
    )

    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "ACTIVE_MOMENTUM_NOT_POSITIVE"
    assert result["opportunity"]["price_series_source"] == "PAIR_BLOCK_HISTORY"


def test_partial_runtime_history_does_not_hide_complete_block_fallback():
    result = _evaluate(
        runtime_prices=[1.20],
    )

    assert result["opportunity_state"] == "WATCH"
    assert result["opportunity_reason"] == "ACTIVE_MOMENTUM_NOT_POSITIVE"
    assert result["opportunity"]["price_series_source"] == "PAIR_BLOCK_HISTORY"


def test_complete_runtime_history_takes_over_after_restart_warmup():
    result = _evaluate(
        runtime_prices=[1.00, 1.01, 1.02],
    )

    assert result["opportunity_state"] == "HOT"
    assert result["opportunity_reason"] == "ACTIVE_CONTINUATION_READY"
    assert result["opportunity"]["price_series_source"] == "PAIR_RUNTIME_ONCHAIN"
