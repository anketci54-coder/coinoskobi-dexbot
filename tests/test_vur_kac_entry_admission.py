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


def test_explicit_normal_trade_type_does_not_enforce_vur_kac_gate():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.02, 1.05],
        quote_reserve_usd=100000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        market_context={
            "runtime_intelligence": {},
        },
        trade_type="NORMAL",
    )

    gate = plan["vur_kac_entry"]

    assert gate["enforced"] is False
    assert gate["ready"] is True
    assert gate["reason"] == (
        "VUR_KAC_ENTRY_GATE_NOT_APPLICABLE"
    )

    assert "VUR_KAC_ENTRY_NOT_READY" not in plan["blockers"]

    assert not any(
        str(value).startswith("VUR_KAC_")
        for value in plan["blockers"]
    )


def test_explicit_vur_kac_trade_type_keeps_strict_gate():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.02, 1.05],
        quote_reserve_usd=100000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        market_context={
            "runtime_intelligence": {},
        },
        trade_type="VUR_KAC",
    )

    gate = plan["vur_kac_entry"]

    assert gate["enforced"] is True
    assert gate["ready"] is False
    assert "VUR_KAC_ENTRY_NOT_READY" in plan["blockers"]


def test_normal_uses_confirmed_hot_active_edge_without_bypassing_admission():
    common = {
        "entry_price": 0.80,
        "available_capital_usdt": 10000.0,
        "price_series": [1.00, 0.70, 0.80],
        "quote_reserve_usd": 50000.0,
        "lp_protected_fraction": 1.0,
        "sellability_status": "SELLABILITY_OK",
        "hard_block": False,
        "sellability_data": _sellability(),
        "exit_evidence": _exit_evidence(),
        "trade_type": "NORMAL",
    }

    stale = build_trade_plan(
        **common,
        market_context={
            "runtime_intelligence": {},
        },
    )

    assert (
        stale["statistics"]["edge_horizon"]["source"]
        == "FULL_OBSERVED_SERIES"
    )
    assert (
        "KNOWN_COMPONENT_EDGE_NOT_POSITIVE"
        in stale["blockers"]
    )

    hot = build_trade_plan(
        **common,
        market_context={
            "runtime_intelligence": {},
            "opportunity": {
                "state": "HOT",
                "reason": "ACTIVE_RECOVERY_BREAKOUT_READY",
                "latest_log_return": 0.13353139262452257,
                "trailing_positive_log_move": 0.13353139262452257,
            },
        },
    )

    assert (
        hot["statistics"]["edge_horizon"]["source"]
        == "CONFIRMED_ACTIVE_OPPORTUNITY"
    )
    assert (
        hot["statistics"]["edge_horizon"]["known_net_log_edge"]
        > 0
    )
    assert (
        "KNOWN_COMPONENT_EDGE_NOT_POSITIVE"
        not in hot["blockers"]
    )
    assert hot["paper_eligible"] is True
    assert hot["capital"]["entry_amount_usdt"] > 0
    assert hot["live_eligible"] is False
    assert hot["wallet_authority"] is False
    assert hot["execution_authority"] is False


def test_normal_watch_opportunity_cannot_override_full_horizon_edge():
    plan = build_trade_plan(
        entry_price=0.80,
        available_capital_usdt=10000.0,
        price_series=[1.00, 0.70, 0.80],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context={
            "runtime_intelligence": {},
            "opportunity": {
                "state": "WATCH",
                "latest_log_return": 0.13353139262452257,
                "trailing_positive_log_move": 0.13353139262452257,
            },
        },
        trade_type="NORMAL",
    )

    assert (
        plan["statistics"]["edge_horizon"]["source"]
        == "FULL_OBSERVED_SERIES"
    )
    assert (
        "KNOWN_COMPONENT_EDGE_NOT_POSITIVE"
        in plan["blockers"]
    )



def test_soft_market_unknowns_stay_observable_without_vetoing_normal():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.02, 1.05],
        quote_reserve_usd=100000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context={
            "runtime_intelligence": {
                "market_quality": {
                    "market_evidence_ready": False,
                    "participation_state": "UNKNOWN",
                    "liquidity_state": "UNKNOWN",
                    "suspicious_volume": None,
                },
            },
        },
        trade_type="NORMAL",
    )

    blockers = set(plan["blockers"])
    unknowns = set(plan["unknowns"])

    assert "MARKET_QUALITY_EVIDENCE_NOT_READY" not in blockers
    assert "PARTICIPATION_EVIDENCE_UNKNOWN" not in blockers
    assert "MARKET_QUALITY_LIQUIDITY_UNKNOWN" not in blockers

    assert "MARKET_QUALITY_EVIDENCE_NOT_READY" in unknowns
    assert "PARTICIPATION_EVIDENCE_UNKNOWN" in unknowns
    assert "MARKET_QUALITY_LIQUIDITY_UNKNOWN" in unknowns

    assert plan["paper_eligible"] is True
    assert plan["live_eligible"] is False
    assert plan["wallet_authority"] is False
    assert plan["execution_authority"] is False


def test_confirmed_adverse_market_quality_still_vetoes_normal():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.02, 1.05],
        quote_reserve_usd=100000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context={
            "runtime_intelligence": {
                "market_quality": {
                    "market_evidence_ready": True,
                    "participation_state": "CONCENTRATED",
                    "liquidity_state": "DETERIORATING_FAST",
                    "suspicious_volume": True,
                },
            },
        },
        trade_type="NORMAL",
    )

    blockers = set(plan["blockers"])

    assert "SUSPICIOUS_VOLUME" in blockers
    assert "PARTICIPATION_CONCENTRATED" in blockers
    assert (
        "MARKET_QUALITY_LIQUIDITY_DETERIORATING_FAST"
        in blockers
    )
    assert plan["paper_eligible"] is False


def test_soft_unknowns_cannot_bypass_strict_vur_kac_flow_gate():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.02, 1.05],
        quote_reserve_usd=100000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context={
            "runtime_intelligence": {
                "market_quality": {
                    "market_evidence_ready": False,
                    "participation_state": "UNKNOWN",
                    "liquidity_state": "UNKNOWN",
                    "suspicious_volume": None,
                },
            },
        },
        trade_type="VUR_KAC",
    )

    assert "VUR_KAC_ENTRY_NOT_READY" in plan["blockers"]
    assert plan["paper_eligible"] is False



def test_absent_market_quality_keeps_unknowns_and_empirical_gate():
    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.05],
        quote_reserve_usd=100000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context={
            "opportunity": {
                "state": "HOT",
                "latest_log_return": 0.04879016416943205,
                "trailing_positive_log_move": 0.04879016416943205,
            },
        },
        trade_type="NORMAL",
    )

    blockers = set(plan["blockers"])
    unknowns = set(plan["unknowns"])

    assert "EMPIRICAL_MOVEMENT_INSUFFICIENT" in blockers
    assert "MARKET_QUALITY_EVIDENCE_NOT_READY" in unknowns
    assert "PARTICIPATION_EVIDENCE_UNKNOWN" in unknowns
    assert "MARKET_QUALITY_LIQUIDITY_UNKNOWN" in unknowns
    assert plan["paper_eligible"] is False
    assert plan["live_eligible"] is False
    assert plan["wallet_authority"] is False
    assert plan["execution_authority"] is False



def test_partial_market_quality_reports_all_soft_unknowns():
    plan = build_trade_plan(
        entry_price=1.10,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.05, 1.10],
        quote_reserve_usd=100000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=_sellability(),
        exit_evidence=_exit_evidence(),
        market_context={
            "opportunity": {
                "state": "HOT",
                "latest_log_return": 0.04652001563489291,
                "trailing_positive_log_move": 0.09531017980432493,
            },
            "market_quality": {},
        },
        trade_type="NORMAL",
    )

    unknowns = set(plan["unknowns"])

    assert "MARKET_QUALITY_EVIDENCE_NOT_READY" in unknowns
    assert "PARTICIPATION_EVIDENCE_UNKNOWN" in unknowns
    assert "MARKET_QUALITY_LIQUIDITY_UNKNOWN" in unknowns
    assert plan["wallet_authority"] is False
    assert plan["execution_authority"] is False
