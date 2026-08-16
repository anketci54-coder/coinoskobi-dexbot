from app.pipeline.simulation_drift import (
    build_simulation_drift,
)
from app.pipeline.simulation_drift_classification import (
    classify_simulation_drift,
)


def assert_safe(result):
    assert result["blocks_trade"] is False
    assert result["blocks_paper"] is False
    assert result["risk_gate_binding"] is False
    assert result["observation_only"] is True

    for field in (
        "trade_authority",
        "decision_authority",
        "paper_authority",
        "live_authority",
        "wallet_authority",
        "signing_authority",
        "execution_authority",
        "hardblock_override_authority",
    ):
        assert result[field] is False


def test_absent_drift_is_unknown():
    result = classify_simulation_drift()

    assert result["state"] == "UNKNOWN"
    assert result["classification"] == "UNKNOWN"
    assert result["severity"] is None
    assert_safe(result)


def test_incomplete_evidence_is_not_bad_drift():
    drift = build_simulation_drift(
        paper_execution={
            "slippage_pct": 0.5,
        },
        observed_execution={
            "slippage_pct": 10.0,
        },
    )

    result = classify_simulation_drift(drift)

    assert result["state"] == "INSUFFICIENT_EVIDENCE"
    assert (
        result["classification"]
        == "INSUFFICIENT_EVIDENCE"
    )
    assert result["severity"] is None
    assert_safe(result)


def test_complete_stable_evidence_is_no_drift():
    drift = build_simulation_drift(
        paper_execution={
            "entry_price": 100,
            "exit_price": 110,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "net_pnl_pct": 5.0,
            "liquidity_usd": 100000,
        },
        observed_execution={
            "entry_price": 100,
            "exit_price": 110,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "net_pnl_pct": 5.0,
            "liquidity_usd": 100000,
        },
    )

    result = classify_simulation_drift(drift)

    assert result["state"] == "CLASSIFIED"
    assert result["classification"] == "NO_DRIFT"
    assert result["severity"] == "NONE"
    assert_safe(result)


def test_liquidity_uses_percentage_not_absolute_delta():
    drift = build_simulation_drift(
        paper_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "liquidity_usd": 100000,
        },
        observed_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "liquidity_usd": 80000,
        },
    )

    result = classify_simulation_drift(drift)

    metric = result["metrics"]["liquidity_drop_pct"]

    assert metric["deterioration"] == 20.0
    assert metric["severity"] == "HIGH"
    assert result["classification"] == "HIGH_DRIFT"
    assert_safe(result)


def test_worse_pnl_is_directionally_classified():
    drift = build_simulation_drift(
        paper_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "net_pnl_pct": 6.0,
        },
        observed_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "net_pnl_pct": 2.5,
        },
    )

    result = classify_simulation_drift(drift)

    metric = result["metrics"]["net_pnl_pct"]

    assert metric["deterioration"] == 3.5
    assert metric["severity"] == "HIGH"
    assert result["classification"] == "HIGH_DRIFT"
    assert_safe(result)


def test_improvement_does_not_create_harmful_drift():
    drift = build_simulation_drift(
        paper_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 1.0,
            "mev_cost_pct": 0.5,
            "quote_delay_ms": 500,
            "execution_delay_ms": 800,
            "net_pnl_pct": 3.0,
        },
        observed_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "net_pnl_pct": 5.0,
        },
    )

    result = classify_simulation_drift(drift)

    assert result["classification"] == "NO_DRIFT"
    assert result["severity"] == "NONE"
    assert_safe(result)


def test_sellability_change_is_visible_but_not_new_block():
    drift = build_simulation_drift(
        paper_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "sellability": "SELLABILITY_OK",
        },
        observed_execution={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 0.5,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "sellability": "SELLABILITY_BLOCKED",
        },
    )

    result = classify_simulation_drift(drift)

    assert result["sellability_changed"] is True
    assert result["blocks_trade"] is False
    assert result["risk_gate_binding"] is False
    assert_safe(result)


def test_phase15_composition_projects_classification():
    from app.pipeline.simulation_drift_composition import (
        build_phase15_drift_composition,
    )

    result = build_phase15_drift_composition(
        paper_position={
            "entry_price": 1,
            "exit_price": 1,
            "slippage": 0.5,
            "net_pnl": 5.0,
            "trade_value": 100.0,
            "liquidity_usd": 100000,
            "sellability": "SELLABILITY_OK",
        },
        runtime_evidence={
            "entry_price": 1,
            "exit_price": 1,
            "slippage_pct": 2.0,
            "net_pnl_pct": 5.0,
            "liquidity_usd": 100000,
            "sellability": "SELLABILITY_OK",
        },
    )

    classification = result["drift_classification"]

    assert (
        result["classification_contract"]
        == "phase15_drift_classification_v1"
    )
    assert classification["classification"] == "HIGH_DRIFT"
    assert classification["severity"] == "HIGH"
    assert classification["blocks_trade"] is False
    assert classification["blocks_paper"] is False
    assert classification["risk_gate_binding"] is False
    assert result["authority_zero"] is True
    assert result["observation_only"] is True


def test_phase15_composition_incomplete_is_not_bad_drift():
    from app.pipeline.simulation_drift_composition import (
        build_phase15_drift_composition,
    )

    result = build_phase15_drift_composition(
        paper_position={
            "slippage_pct": 0.5,
        },
        runtime_evidence={
            "slippage_pct": 10.0,
        },
    )

    classification = result["drift_classification"]

    assert (
        classification["classification"]
        == "INSUFFICIENT_EVIDENCE"
    )
    assert classification["severity"] is None
    assert classification["blocks_trade"] is False
    assert classification["risk_gate_binding"] is False
