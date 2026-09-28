from app.risk.execution_envelope import (
    build_minout_envelope,
    empirical_quote_drift,
)
from app.risk.mev import mev_loss_envelope


def samples(*pairs):
    return [
        {
            "block": index,
            "token_reserve": token,
            "quote_reserve": quote,
        }
        for index, (token, quote)
        in enumerate(pairs, start=1)
    ]


def test_exact_size_sell_quote_drift_detects_adverse_reserve_move():
    result = empirical_quote_drift(
        reserve_samples=samples(
            (1000, 1000),
            (1010, 990),
            (1020, 980),
            (1030, 970),
        ),
        amount_in=10,
        fee_fraction=0.0025,
        side="SELL",
    )

    assert result["state"] == "READY"
    assert result["sample_count"] == 4
    assert result["worst_adverse_drift_fraction"] > 0
    assert (
        result["quotes"][-1]["amount_out"]
        < result["quotes"][0]["amount_out"]
    )


def test_stable_reserves_require_no_invented_slippage_headroom():
    drift = empirical_quote_drift(
        reserve_samples=samples(
            (1000, 1000),
            (1000, 1000),
            (1000, 1000),
            (1000, 1000),
        ),
        amount_in=10,
        fee_fraction=0.0025,
        side="SELL",
    )

    envelope = build_minout_envelope(
        baseline_executable_output_usd=100.0,
        quote_drift_fraction=(
            drift["worst_adverse_drift_fraction"]
        ),
    )

    assert drift["worst_adverse_drift_fraction"] == 0.0
    assert envelope["state"] == "BOUNDED"
    assert envelope["slippage_tolerance_pct"] == 0.0
    assert envelope["min_out_fraction"] == 1.0
    assert envelope["adverse_execution_reserve_usd"] == 0.0


def test_minout_headroom_is_same_total_bound_used_by_mev_envelope():
    envelope = build_minout_envelope(
        baseline_executable_output_usd=1000.0,
        quote_drift_fraction=0.0125,
    )
    mev = mev_loss_envelope(
        baseline_executable_output_usd=1000.0,
        slippage_tolerance_pct=(
            envelope["slippage_tolerance_pct"]
        ),
        route_visibility="PUBLIC",
    )

    assert envelope["state"] == "BOUNDED"
    assert mev["state"] == "BOUNDED"
    assert (
        mev["decision_reserve_usd"]
        == envelope["adverse_execution_reserve_usd"]
        == 12.5
    )


def test_measured_drift_cannot_widen_beyond_edge_budget():
    result = build_minout_envelope(
        baseline_executable_output_usd=1000.0,
        quote_drift_fraction=0.03,
        edge_budget_fraction=0.02,
    )

    assert result["state"] == "EDGE_BUDGET_EXCEEDED"
    assert result["adverse_execution_reserve_usd"] == 30.0
    assert result["edge_budget_fraction"] == 0.02


def test_missing_quote_history_stays_unknown():
    result = empirical_quote_drift(
        reserve_samples=samples(
            (1000, 1000),
        ),
        amount_in=10,
        fee_fraction=0.0025,
        side="SELL",
    )

    assert result["state"] == "UNKNOWN"
    assert result["reason"] == "QUOTE_HISTORY_INSUFFICIENT"


def test_invalid_minout_inputs_are_unbounded_not_zero():
    result = build_minout_envelope(
        baseline_executable_output_usd=None,
        quote_drift_fraction=0.01,
    )

    assert result["state"] == "UNBOUNDED"
    assert result["adverse_execution_reserve_usd"] is None


def test_sizing_shadow_produces_bounded_exact_size_envelope():
    from app.risk.paper_position_sizing import _execution_envelope_shadow

    plan = {
        "entry": {"price": 1.0},
        "cost_model": {"buy_tax_fraction": 0.0},
        "expected": {"known_net_edge_fraction": 0.05},
        "execution_economics": {
            "implied_v2_fee_state": "READY",
            "implied_v2_fee_fraction": 0.0025,
            "reserve_samples": samples(
                (1000, 1000),
                (1000, 1000),
                (1000, 1000),
                (1000, 1000),
            ),
        },
    }

    result = _execution_envelope_shadow(
        plan,
        10.0,
    )

    assert result["state"] == "BOUNDED"
    assert result["would_block"] is False
    assert result["sample_count"] == 4
    assert result["slippage_tolerance_pct"] == 0.0
    assert result["baseline_executable_output_usd"] > 0


def test_sizing_shadow_flags_measured_drift_beyond_edge_budget():
    from app.risk.paper_position_sizing import _execution_envelope_shadow

    plan = {
        "entry": {"price": 1.0},
        "cost_model": {"buy_tax_fraction": 0.0},
        "expected": {"known_net_edge_fraction": 0.001},
        "execution_economics": {
            "implied_v2_fee_state": "READY",
            "implied_v2_fee_fraction": 0.0025,
            "reserve_samples": samples(
                (1000, 1000),
                (990, 1010),
                (980, 1020),
                (970, 1030),
            ),
        },
    }

    result = _execution_envelope_shadow(
        plan,
        10.0,
    )

    assert result["state"] == "EDGE_BUDGET_EXCEEDED"
    assert result["would_block"] is True
    assert result["adverse_execution_reserve_usd"] > 0


from app.dex.price_impact import constant_product_quote
from app.risk.execution_envelope import derive_buy_execution_economics


def _exit_evidence(
    *,
    block=100,
    token_reserve=1000.0,
    quote_reserve=1000.0,
    fee=0.0025,
    wbnb_usd=600.0,
    samples=None,
):
    if samples is None:
        samples = [
            {"block": block - 3, "token_reserve": token_reserve, "quote_reserve": quote_reserve},
            {"block": block - 2, "token_reserve": token_reserve, "quote_reserve": quote_reserve},
            {"block": block - 1, "token_reserve": token_reserve, "quote_reserve": quote_reserve},
            {"block": block, "token_reserve": token_reserve, "quote_reserve": quote_reserve},
        ]
    return {
        "runtime_price_latest_block": block,
        "token_decimals": 18,
        "implied_v2_fee_state": "READY",
        "implied_v2_fee_fraction": fee,
        "reserve_samples": samples,
        "wbnb_usd_estimate": wbnb_usd,
    }


def _buy(*, block=100, received_token, gas_wei=200_000_000_000_000):
    return {
        "buy": {
            "status": "SUCCESS",
            "block": {"number": block, "chain_id": 56},
            "received_token_raw": int(round(received_token * 10**18)),
            "gas_used": 200000,
            "effective_gas_price": 1_000_000_000,
            "execution_gas_cost_wei": gas_wei,
        }
    }


def test_buy_execution_economics_no_transfer_loss_uses_exact_route_delta():
    exit_evidence = _exit_evidence()
    exact = constant_product_quote(
        reserve_in=1000.0,
        reserve_out=1000.0,
        amount_in=10.0,
        fee_fraction=0.0025,
    )["amount_out"]

    result = derive_buy_execution_economics(
        buy_evidence=_buy(received_token=exact),
        exit_evidence=exit_evidence,
        entry_amount_usdt=10.0,
        known_edge_fraction=0.05,
    )

    assert result["state"] == "READY"
    assert abs(result["buy_transfer_retention"] - 1.0) < 1e-12
    assert result["buy_transfer_loss_fraction"] < 1e-12
    assert abs(result["buy_gas_usd"] - 0.12) < 1e-12
    assert result["quote_drift_fraction"] == 0.0
    assert result["slippage_tolerance_pct"] == 0.0
    assert result["total_adverse_execution_reserve_usd"] == 0.0
    assert result["mev_upper_bound_usd"] == 0.0
    assert result["mev_and_natural_drift_are_additive"] is False


def test_buy_execution_economics_measures_transfer_loss_from_balance_delta():
    exit_evidence = _exit_evidence()
    exact = constant_product_quote(
        reserve_in=1000.0,
        reserve_out=1000.0,
        amount_in=10.0,
        fee_fraction=0.0025,
    )["amount_out"]

    result = derive_buy_execution_economics(
        buy_evidence=_buy(received_token=exact * 0.95),
        exit_evidence=exit_evidence,
        entry_amount_usdt=10.0,
        known_edge_fraction=0.10,
    )

    assert result["state"] == "READY"
    assert abs(result["buy_transfer_retention"] - 0.95) < 1e-12
    assert abs(result["buy_transfer_loss_fraction"] - 0.05) < 1e-12
    assert result["deterministic_buy_shortfall_usd"] > 0


def test_buy_execution_economics_rejects_block_mismatch():
    exact = constant_product_quote(
        reserve_in=1000.0,
        reserve_out=1000.0,
        amount_in=10.0,
        fee_fraction=0.0025,
    )["amount_out"]

    result = derive_buy_execution_economics(
        buy_evidence=_buy(block=101, received_token=exact),
        exit_evidence=_exit_evidence(block=100),
        entry_amount_usdt=10.0,
        known_edge_fraction=0.05,
    )

    assert result["state"] == "UNKNOWN"
    assert result["reason"] == "PINNED_BLOCK_MISMATCH_OR_AMOUNT_UNKNOWN"
    assert result["block_match"] is False


def test_buy_execution_economics_keeps_gas_unknown_without_bnb_usd():
    exit_evidence = _exit_evidence(wbnb_usd=None)
    exact = constant_product_quote(
        reserve_in=1000.0,
        reserve_out=1000.0,
        amount_in=10.0,
        fee_fraction=0.0025,
    )["amount_out"]

    result = derive_buy_execution_economics(
        buy_evidence=_buy(received_token=exact),
        exit_evidence=exit_evidence,
        entry_amount_usdt=10.0,
        known_edge_fraction=0.05,
    )

    assert result["state"] == "READY"
    assert result["buy_gas_usd"] is None


def test_buy_execution_economics_flags_quote_drift_beyond_edge_budget():
    samples = [
        {"block": 97, "token_reserve": 1000.0, "quote_reserve": 1000.0},
        {"block": 98, "token_reserve": 990.0, "quote_reserve": 1010.0},
        {"block": 99, "token_reserve": 980.0, "quote_reserve": 1020.0},
        {"block": 100, "token_reserve": 970.0, "quote_reserve": 1030.0},
    ]
    exit_evidence = _exit_evidence(
        block=100,
        token_reserve=970.0,
        quote_reserve=1030.0,
        samples=samples,
    )
    exact = constant_product_quote(
        reserve_in=1030.0,
        reserve_out=970.0,
        amount_in=10.0,
        fee_fraction=0.0025,
    )["amount_out"]

    result = derive_buy_execution_economics(
        buy_evidence=_buy(received_token=exact),
        exit_evidence=exit_evidence,
        entry_amount_usdt=10.0,
        known_edge_fraction=0.001,
    )

    assert result["state"] == "EDGE_BUDGET_EXCEEDED"
    assert result["quote_drift_fraction"] > 0.001
    assert result["total_adverse_execution_reserve_usd"] > 0
