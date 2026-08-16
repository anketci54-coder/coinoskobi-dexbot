from app.pipeline.simulation_drift import (
    build_simulation_drift,
)


def assert_authority_zero(result):
    assert result["executed"] is False
    assert result["provider_call"] is False
    assert result["external_fetch"] is False
    assert result["wallet_use"] is False
    assert result["signing"] is False

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


def test_simulation_drift_compares_execution_truth():
    result = build_simulation_drift(
        paper_execution={
            "entry_price": 100,
            "exit_price": 110,
            "slippage_pct": 0.5,
            "gas_cost_usd": 0.25,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "net_pnl_pct": 9.0,
            "liquidity_usd": 100000,
            "sellability": "SELLABILITY_OK",
        },
        observed_execution={
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
        == "phase15_simulation_drift_v1"
    )

    assert (
        result["drift"]["entry_price"]["delta"]
        == 1.0
    )

    assert (
        result["drift"]["exit_price"]["delta"]
        == -3.0
    )

    assert (
        result["drift"]["slippage_pct"]["delta"]
        == 0.7
    )

    assert (
        result["drift"]["net_pnl_pct"]["delta"]
        == -3.5
    )

    assert (
        result["liquidity"]["delta_usd"]
        == -20000.0
    )

    assert (
        result["sellability"]["changed"]
        is False
    )

    assert result["comparison_complete"] is True
    assert_authority_zero(result)


def test_missing_observed_truth_stays_unknown():
    result = build_simulation_drift(
        paper_execution={
            "entry_price": 100,
            "net_pnl_pct": 5,
        },
        observed_execution={},
    )

    assert (
        result["drift"]["entry_price"]["observed"]
        is None
    )
    assert (
        result["drift"]["entry_price"]["delta"]
        is None
    )
    assert (
        result["drift"]["net_pnl_pct"]["delta"]
        is None
    )

    assert result["comparison_complete"] is False
    assert_authority_zero(result)


def test_sellability_deterioration_is_visible():
    result = build_simulation_drift(
        paper_execution={
            "sellability": "SELLABILITY_OK",
        },
        observed_execution={
            "sellability": "SELLABILITY_BLOCKED",
        },
    )

    assert (
        result["sellability"]["changed"]
        is True
    )

    assert (
        result["sellability"]["observed"]
        == "SELLABILITY_BLOCKED"
    )

    assert_authority_zero(result)


def test_invalid_numeric_evidence_is_not_invented():
    result = build_simulation_drift(
        paper_execution={
            "slippage_pct": "unknown",
        },
        observed_execution={
            "slippage_pct": "bad-data",
        },
    )

    assert (
        result["drift"]["slippage_pct"]["paper"]
        is None
    )
    assert (
        result["drift"]["slippage_pct"]["observed"]
        is None
    )
    assert (
        result["drift"]["slippage_pct"]["delta"]
        is None
    )

    assert_authority_zero(result)
