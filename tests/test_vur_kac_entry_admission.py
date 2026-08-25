from app.strategy.mathematical_trade_plan import (
    build_trade_plan,
)


def _sellability():
    return {
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "buy_gas": 0.0,
        "sell_gas": 0.0,
    }


def _exit_evidence():
    return {
        "route_friction_fraction": 0.0,
        "gas_price_wei": 0.0,
        "wbnb_usd_estimate": 600.0,
    }


def _runtime_context(flow):
    return {
        "runtime_intelligence": {},
        "flow_intelligence": flow,
    }


def test_runtime_vur_kac_entry_blocks_weakening_price_momentum():
    plan = build_trade_plan(
        entry_price=1.15,
        available_capital_usdt=10000.0,
        price_series=[
            1.00,
            1.10,
            1.15,
        ],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context=_runtime_context({
            "buy_flow": 8,
            "sell_flow": 2,
            "prev_spread": 3,
            "prev_velocity": 1,
            "freshness": "FRESH",
            "coverage": 1.0,
        }),
    )

    assert plan["expected"][
        "known_net_edge_fraction"
    ] > 0

    assert plan["paper_eligible"] is False

    assert (
        "VUR_KAC_ENTRY_NOT_READY"
        in plan["blockers"]
    )

    assert (
        "VUR_KAC_PRICE_ACCELERATION_WEAKENING"
        in plan["blockers"]
    )

    gate = plan["vur_kac_entry"]

    assert gate["enforced"] is True
    assert gate["ready"] is False
    assert (
        gate["reason"]
        == "VUR_KAC_PRICE_ACCELERATION_WEAKENING"
    )


def test_runtime_vur_kac_entry_allows_positive_price_and_flow_continuation():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[
            1.00,
            1.02,
            1.05,
        ],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context=_runtime_context({
            "buy_flow": 8,
            "sell_flow": 2,
            "prev_spread": 3,
            "prev_velocity": 1,
            "freshness": "FRESH",
            "coverage": 1.0,
        }),
    )

    blockers = set(plan["blockers"])

    assert "VUR_KAC_ENTRY_NOT_READY" not in blockers
    assert plan["paper_eligible"] is True

    gate = plan["vur_kac_entry"]

    assert gate["enforced"] is True
    assert gate["ready"] is True
    assert (
        gate["reason"]
        == "VUR_KAC_ENTRY_SIGNAL_READY"
    )
    assert gate["latest_log_return"] > 0
    assert gate["price_acceleration"] >= 0
    assert gate["flow_momentum"] > 0
    assert gate["flow_acceleration"] >= 0


def test_non_runtime_trade_plan_call_remains_backwards_compatible():
    plan = build_trade_plan(
        entry_price=1.04,
        available_capital_usdt=1000.0,
        price_series=[
            1.00,
            1.02,
            1.04,
        ],
        quote_reserve_usd=10000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context=None,
    )

    assert plan["paper_eligible"] is True
    assert (
        "VUR_KAC_ENTRY_NOT_READY"
        not in plan["blockers"]
    )
    assert (
        plan["vur_kac_entry"]["reason"]
        == "VUR_KAC_ENTRY_GATE_NOT_APPLICABLE"
    )
