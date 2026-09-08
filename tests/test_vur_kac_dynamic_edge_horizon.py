import math

from app.strategy.mathematical_trade_plan import build_trade_plan


def _base_context(*, buy_flow=10.0, sell_flow=2.0):
    return {
        "runtime_intelligence": {},
        "flow_intelligence": {
            "freshness": "FRESH",
            "coverage": 1.0,
            "buy_flow": buy_flow,
            "sell_flow": sell_flow,
            "prev_spread": 6.0,
            "prev_velocity": 0.0,
        },
    }


def _exit():
    return {
        "route_friction_fraction": 0.0025,
        "gas_price_wei": 1_000_000_000,
        "wbnb_usd_estimate": 600.0,
        "observed_min_quote_reserve_usd": 100_000.0,
        "reserve_observation_count": 3,
    }


def _sellability():
    return {
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "buy_gas": 100_000,
        "sell_gas": 100_000,
    }


def test_runtime_ready_uses_trailing_positive_continuation():
    prices = [100.0, 50.0, 25.0, 26.0, 28.0]

    plan = build_trade_plan(
        entry_price=28.0,
        available_capital_usdt=1000.0,
        price_series=prices,
        quote_reserve_usd=100_000.0,
        lp_protected_fraction=1.0,
        sellability_status="OK",
        sellability_data=_sellability(),
        exit_evidence=_exit(),
        market_context=_base_context(),
    )

    edge = plan["statistics"]["edge_horizon"]

    assert edge["source"] == "TRAILING_POSITIVE_CONTINUATION"
    assert edge["full_horizon_log_move"] < 0
    assert edge["trailing_positive_return_count"] == 2
    assert edge["effective_gross_log_edge"] > 0
    assert edge["known_net_log_edge"] > 0
    assert "KNOWN_COMPONENT_EDGE_NOT_POSITIVE" not in plan["blockers"]
    assert "MATHEMATICAL_POSITION_SIZE_ZERO" not in plan["blockers"]
    assert plan["capital"]["entry_amount_usdt"] > 0
    assert plan["live_eligible"] is False
    assert plan["wallet_authority"] is False
    assert plan["execution_authority"] is False


def test_non_runtime_keeps_full_observed_series_edge():
    prices = [100.0, 50.0, 25.0, 26.0, 28.0]

    plan = build_trade_plan(
        entry_price=28.0,
        available_capital_usdt=1000.0,
        price_series=prices,
        quote_reserve_usd=100_000.0,
        lp_protected_fraction=1.0,
        sellability_status="OK",
        sellability_data=_sellability(),
        exit_evidence=_exit(),
        market_context={},
    )

    edge = plan["statistics"]["edge_horizon"]

    assert edge["source"] == "FULL_OBSERVED_SERIES"
    assert math.isclose(
        edge["effective_gross_log_edge"],
        plan["statistics"]["horizon_log_move"],
        rel_tol=0,
        abs_tol=1e-12,
    )


def test_hard_market_blockers_are_not_bypassed():
    context = _base_context()
    context["market_quality"] = {
        "market_evidence_ready": True,
        "participation_state": "CONCENTRATED",
        "liquidity_state": "READY",
        "suspicious_volume": True,
    }

    plan = build_trade_plan(
        entry_price=28.0,
        available_capital_usdt=1000.0,
        price_series=[100.0, 50.0, 25.0, 26.0, 28.0],
        quote_reserve_usd=100_000.0,
        lp_protected_fraction=1.0,
        sellability_status="OK",
        sellability_data=_sellability(),
        exit_evidence=_exit(),
        market_context=context,
    )

    assert "PARTICIPATION_CONCENTRATED" in plan["blockers"]
    assert "SUSPICIOUS_VOLUME" in plan["blockers"]
    assert plan["paper_eligible"] is False
