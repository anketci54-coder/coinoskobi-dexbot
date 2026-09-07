from app.paper.manager import PaperManager
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


def test_price_continuation_can_enter_while_flow_evidence_matures():
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
        market_context={
            "runtime_intelligence": {},
            "flow_intelligence": None,
        },
    )

    assert plan["paper_eligible"] is True
    assert plan["blockers"] == []
    assert plan["capital"]["entry_amount_usdt"] > 0

    admission = plan["paper_admission"]

    assert (
        admission["mode"]
        == "EARLY_PRICE_CONTINUATION"
    )

    assert set(
        admission[
            "bypassed_soft_blockers"
        ]
    ) == {
        "VUR_KAC_ENTRY_NOT_READY",
        "VUR_KAC_FLOW_EVIDENCE_NOT_READY",
    }

    assert (
        admission["hard_safety_bypassed"]
        is False
    )

    assert (
        admission["economic_edge_bypassed"]
        is False
    )


def test_weakening_price_cannot_use_early_admission():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[
            1.00,
            1.04,
            1.05,
        ],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context={
            "runtime_intelligence": {},
            "flow_intelligence": None,
        },
    )

    assert plan["paper_eligible"] is False

    # Flow evidence is evaluated before the directional
    # reason is emitted, so the canonical blocker remains
    # FLOW_EVIDENCE_NOT_READY. Early admission must still
    # refuse weakening price acceleration.
    assert (
        "VUR_KAC_FLOW_EVIDENCE_NOT_READY"
        in plan["blockers"]
    )

    gate = plan["vur_kac_entry"]

    assert gate["latest_log_return"] > 0
    assert gate["previous_log_return"] > 0
    assert gate["price_acceleration"] < 0

    admission = plan["paper_admission"]

    assert (
        admission["early_price_continuation"]
        is False
    )

    assert (
        admission["mode"]
        == "BLOCKED"
    )


def test_break_even_floor_arms_only_after_real_break_even():
    pos = {
        "entry_amount_usdt": 100.0,
        "token_amount": 100.0,
    }

    plan = {
        "cost_model": {
            "sell_retention_known": 0.99,
            "sell_gas_usd": 1.0,
        }
    }

    stop, floor, armed = (
        PaperManager._profit_protection_floor(
            pos=pos,
            plan=plan,
            highest=1.03,
            current_stop=0.90,
        )
    )

    assert armed is True
    assert floor > 1.0
    assert stop == floor

    stop, floor, armed = (
        PaperManager._profit_protection_floor(
            pos=pos,
            plan=plan,
            highest=1.01,
            current_stop=0.90,
        )
    )

    assert armed is False
    assert stop == 0.90


def test_never_positive_and_still_falling_exits_early():
    assert PaperManager._no_upside_failure(
        post_entry_history=[
            0.99,
            0.97,
        ],
        entry_price=1.0,
        highest=1.0,
        current=0.97,
    ) is True


def test_prior_upside_or_recovery_does_not_false_trigger():
    assert PaperManager._no_upside_failure(
        post_entry_history=[
            1.01,
            0.99,
        ],
        entry_price=1.0,
        highest=1.01,
        current=0.99,
    ) is False

    assert PaperManager._no_upside_failure(
        post_entry_history=[
            0.97,
            0.99,
        ],
        entry_price=1.0,
        highest=1.0,
        current=0.99,
    ) is False
