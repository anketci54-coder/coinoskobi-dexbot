from app.pipeline.simulation_drift_composition import (
    build_phase15_drift_composition,
)


def assert_authority_zero(result):
    assert result["provider_call"] is False
    assert result["external_fetch"] is False
    assert result["wallet_use"] is False
    assert result["signing"] is False
    assert result["executed"] is False

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

    assert result["authority_zero"] is True
    assert result["safety_zero"] is True


def test_phase15c_composes_evidence_into_drift():
    result = build_phase15_drift_composition(
        paper_position={
            "entry_price": 100,
            "exit_price": 110,
            "slippage": 0.5,
            "trade_value": 1000,
            "net_pnl": 90,
            "liquidity_usd": 100000,
            "sellability": "SELLABILITY_OK",
        },
        runtime_evidence={
            "entry_price": 101,
            "exit_price": 107,
            "slippage_pct": 1.2,
            "gas_cost_usd": 0.40,
            "mev_cost_pct": 0.3,
            "quote_delay_ms": 180,
            "execution_delay_ms": 400,
            "net_pnl_pct": 5.5,
            "liquidity_usd": 80000,
            "sellability": "SELLABILITY_OK",
        },
    )

    assert (
        result["contract"]
        == "phase15_drift_composition_v1"
    )

    assert (
        result["evidence_contract"]
        == "phase15_execution_evidence_v1"
    )

    assert (
        result["drift_contract"]
        == "phase15_simulation_drift_v1"
    )

    drift = result["simulation_drift"]

    assert (
        drift["drift"]["entry_price"]["delta"]
        == 1.0
    )

    assert (
        drift["drift"]["exit_price"]["delta"]
        == -3.0
    )

    assert (
        drift["drift"]["slippage_pct"]["delta"]
        == 0.7
    )

    assert (
        drift["drift"]["net_pnl_pct"]["delta"]
        == -3.5
    )

    assert (
        drift["liquidity"]["delta_usd"]
        == -20000.0
    )

    assert result["comparison_complete"] is True

    assert_authority_zero(result)


def test_phase15c_preserves_missing_observed_truth():
    result = build_phase15_drift_composition(
        paper_position={
            "entry_price": 1.0,
        },
        runtime_evidence={},
    )

    assert (
        result["observed_evidence_count"]
        == 0
    )

    assert (
        result["observed_evidence_complete"]
        is False
    )

    assert (
        result["comparison_complete"]
        is False
    )

    assert (
        result["simulation_drift"][
            "drift"
        ]["entry_price"]["observed"]
        is None
    )

    assert "exit_price" in (
        result["missing_observed_fields"]
    )

    assert_authority_zero(result)


def test_phase15c_derives_explicit_execution_delay():
    result = build_phase15_drift_composition(
        runtime_evidence={
            "execution_started_at": (
                "2026-01-01T00:00:00+00:00"
            ),
            "execution_observed_at": (
                "2026-01-01T00:00:00.250+00:00"
            ),
        }
    )

    observed = (
        result["execution_evidence"][
            "observed_execution"
        ]
    )

    assert (
        observed["execution_delay_ms"]
        == 250.0
    )

    assert_authority_zero(result)


def test_phase15c_does_not_invent_gas_usd():
    result = build_phase15_drift_composition(
        paper_position={
            "entry_price": 1.0,
            "gas_buy": 0.001,
            "gas_sell": 0.002,
        },
        runtime_evidence={},
    )

    evidence = result["execution_evidence"]

    assert (
        evidence["paper_execution"][
            "gas_cost_usd"
        ]
        is None
    )

    assert (
        evidence["paper_native_evidence"][
            "gas_buy"
        ]
        == 0.001
    )

    assert (
        evidence["paper_native_evidence"][
            "gas_sell"
        ]
        == 0.002
    )

    assert_authority_zero(result)


def test_phase15c_sellability_deterioration_visible():
    result = build_phase15_drift_composition(
        paper_position={
            "sellability": "SELLABILITY_OK",
        },
        runtime_evidence={
            "sellability": (
                "SELLABILITY_BLOCKED"
            ),
        },
    )

    assert (
        result["simulation_drift"][
            "sellability"
        ]["changed"]
        is True
    )

    assert_authority_zero(result)
