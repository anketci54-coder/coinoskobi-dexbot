from app.pipeline.simulation_drift_evidence import (
    build_phase15_execution_evidence,
)


def _assert_zero_authority(result):
    for key in (
        "provider_call", "external_fetch", "wallet_use", "signing",
        "executed", "trade_authority", "decision_authority",
        "paper_authority", "live_authority", "wallet_authority",
        "signing_authority", "execution_authority",
        "hardblock_override_authority",
    ):
        assert result[key] is False


def test_binds_existing_paper_truth_without_inventing_units():
    result = build_phase15_execution_evidence(
        paper_position={
            "entry_price": 1.0,
            "exit_price": 1.2,
            "slippage": 0.5,
            "gas_buy": 0.001,
            "gas_sell": 0.002,
            "net_pnl": 0.2,
            "created_at": "2026-01-01T00:00:00+00:00",
            "closed_at": "2026-01-01T00:01:00+00:00",
        }
    )
    paper = result["paper_execution"]
    assert paper["entry_price"] == 1.0
    assert paper["exit_price"] == 1.2
    assert paper["slippage_pct"] == 0.5
    assert paper["gas_cost_usd"] is None
    assert paper["net_pnl_pct"] is None
    assert result["paper_native_evidence"]["gas_buy"] == 0.001
    _assert_zero_authority(result)


def test_missing_runtime_truth_remains_unknown():
    result = build_phase15_execution_evidence(
        paper_position={"entry_price": 1.0},
        runtime_evidence={},
    )
    assert result["observed_evidence_count"] == 0
    assert result["observed_evidence_complete"] is False
    assert "exit_price" in result["missing_observed_fields"]
    _assert_zero_authority(result)


def test_supplied_runtime_evidence_is_normalized_only():
    result = build_phase15_execution_evidence(
        runtime_evidence={
            "entry_price": "1.01",
            "exit_price": 1.18,
            "slippage_pct": 0.8,
            "gas_cost_usd": 0.12,
            "liquidity_usd": 90000,
            "sellability": "SELLABILITY_OK",
        }
    )
    observed = result["observed_execution"]
    assert observed["entry_price"] == 1.01
    assert observed["gas_cost_usd"] == 0.12
    assert result["observed_evidence_complete"] is True
    _assert_zero_authority(result)


def test_execution_delay_may_be_derived_from_explicit_timestamps():
    result = build_phase15_execution_evidence(
        runtime_evidence={
            "execution_started_at": "2026-01-01T00:00:00+00:00",
            "execution_observed_at": "2026-01-01T00:00:00.250+00:00",
        }
    )
    assert result["observed_execution"]["execution_delay_ms"] == 250.0
    _assert_zero_authority(result)
