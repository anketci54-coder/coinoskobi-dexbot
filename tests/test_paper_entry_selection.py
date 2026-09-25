"""Decision-time replays; later WATCH probe returns are never plan inputs."""
from types import SimpleNamespace

import pytest

from app.config.contracts import USDT, WBNB
from app.pipeline import engine
from app.pipeline.runtime_price_history import RuntimePriceHistory
from app.risk.paper_position_sizing import calculate_paper_position_size
from app.strategy.mathematical_trade_plan import build_trade_plan
from app.strategy.unified_score import UnifiedScoreEngine


@pytest.fixture
def history(monkeypatch):
    monkeypatch.setattr(engine, "_RUNTIME_PRICE_HISTORY", RuntimePriceHistory())
    monkeypatch.setattr(
        "app.risk.paper_position_sizing._empirical_outcome_calibration",
        lambda **_: dict(gap_multiplier=1.0, cost_uncertainty_fraction=0.0,
                        account_risk_budget_fraction=0.01,
                        gap_samples=3, cost_samples=3, account_risk_samples=3),
    )


def observe(prices):
    return engine._runtime_math_evidence(
        token_address="0xtoken", pool="0xpool", price=prices[-1],
        upstream_price_series=prices, price_series_source="PAIR_RUNTIME_ONCHAIN",
        exit_evidence={}, lp_evidence={}, sellability_data={},
        market_context={"candidate_quote_token": USDT},
    )["price_series"]


def plan(prices, **overrides):
    opportunity = UnifiedScoreEngine._opportunity_state(
        strategy={"decision": "PAPER_BUY"},
        risk_gate={"local_evidence": {"exit_feasibility": {
            "runtime_spot_price_series_usd": prices,
            "quote_reserve_usd": 50000, "latest_reserve_change_fraction": 0,
        }}}, mev_risk={"status": "LOW_EXPOSURE"},
    )
    args = dict(
        entry_price=prices[-1], available_capital_usdt=10000,
        price_series=prices, quote_reserve_usd=50000, lp_protected_fraction=1,
        sellability_status="SELLABILITY_OK", trade_type="NORMAL",
        sellability_data=dict(buy_tax=0, sell_tax=0, buy_gas=0, sell_gas=0),
        exit_evidence=dict(route_friction_fraction=0, gas_price_wei=0,
                           wbnb_usd_estimate=600),
        market_context={"candidate_quote_token": USDT,
                        "opportunity": opportunity,
                        "plan_price_series_source": "PAIR_RUNTIME_ONCHAIN"},
    )
    args.update(overrides)
    return build_trade_plan(**args)


@pytest.mark.parametrize("prices", [[1, 1.5, 1.3], [1, 1.2, 1.5, 1.5]])
def test_old_gain_cannot_admit_nonpositive_current_momentum(history, prices):
    p = plan(prices)
    assert p["expected"]["known_net_edge_fraction"] > 0
    assert "NORMAL_ACTIVE_MOMENTUM_NOT_POSITIVE" in p["blockers"]
    assert p["paper_eligible"] is False
    assert calculate_paper_position_size(mathematical_plan=p)["entry_amount_usdt"] == 0


def test_usdt_watch_can_qualify_when_real_observations_arrive(history):
    # Verified profitable USDT probes were predominantly single-observation
    # WATCHes. They must stay blocked then, but not lose new upstream samples.
    first = plan(observe([1]))
    assert first["paper_eligible"] is False
    assert "EMPIRICAL_MOVEMENT_INSUFFICIENT" in first["blockers"]
    prices = observe([1, 1.04, 1.06])
    assert prices == [1, 1.04, 1.06]
    qualified = plan(prices)
    assert qualified["paper_eligible"] is True
    sized = calculate_paper_position_size(mathematical_plan=qualified)
    assert sized["entry_amount_usdt"] > 0
    assert sized["immediate_entry_allowed"] is True


def test_repeated_snapshot_does_not_manufacture_a_flat_return(history):
    prices = [1, 1.04, 1.06]
    assert observe(prices) == prices
    assert observe(prices) == prices


def test_upstream_reset_does_not_reuse_stale_profitable_history(history):
    observe([1, 1.04, 1.06])
    assert observe([1.06]) == [1.06]
    assert plan(observe([1.06]))["paper_eligible"] is False


def test_block_fallback_uses_current_snapshot_not_provider_history(history):
    from datetime import datetime, timezone
    common = dict(token_address="0xtoken", pool="0xpool", price=1.1,
        price_series_source="PAIR_BLOCK_HISTORY", exit_evidence={}, lp_evidence={},
        market_context={}, sellability_data={})
    row = dict(token="0xtoken", pool="0xpool", price_usd=100,
               source="dexscreener", observed_at=datetime.now(timezone.utc).isoformat())
    first = engine._runtime_math_evidence(**common,
        upstream_price_series=[1, 1.1], durable_pair_history=[row])
    assert first["price_series"] == [1, 1.1]
    second = engine._runtime_math_evidence(**common, upstream_price_series=[1.1, .9])
    assert second["price_series"] == [1.1, .9]


@pytest.mark.parametrize("source", ["PAIR_RUNTIME_ONCHAIN", "PAIR_BLOCK_HISTORY"])
def test_pair_snapshot_revisits_resets_and_pools_remain_isolated(history, source):
    common = dict(token_address="0xtoken", pool="0xpool", price=100,
        price_series_source=source, exit_evidence={}, lp_evidence={},
        market_context={}, sellability_data={})

    def snapshot(prices, **overrides):
        return engine._runtime_math_evidence(
            **{**common, **overrides}, upstream_price_series=prices)["price_series"]

    assert snapshot([1, 1.04, 1.06]) == [1, 1.04, 1.06]
    assert snapshot([100], price_series_source="TOKEN_CACHE") == [100]
    assert snapshot([8, 7], pool="0xotherpool") == [8, 7]
    assert snapshot([1, 1.04, 1.06]) == [1, 1.04, 1.06]
    assert snapshot([]) == []
    assert snapshot([1.06]) == [1.06]
    assert plan(snapshot([1.06]))["paper_eligible"] is False


@pytest.mark.parametrize("overrides", [
    {"sellability_status": "SELLABILITY_FAIL"},
    {"hard_block": True},
    {"quote_reserve_usd": 0},
    {"lp_protected_fraction": None},
    {"sellability_data": dict(buy_tax=10, sell_tax=10, buy_gas=0, sell_gas=0)},
])
def test_apparent_pump_cannot_bypass_safety(history, overrides):
    p = plan(observe([1, 1.04, 1.06]), **overrides)
    sized = calculate_paper_position_size(mathematical_plan=p)
    assert sized["entry_amount_usdt"] == 0


def test_sellability_unknown_allowed_for_paper_observation(history):
    p = plan(
        observe([1, 1.04, 1.06]),
        sellability_status="SELLABILITY_UNKNOWN",
    )
    sized = calculate_paper_position_size(mathematical_plan=p)
    assert sized["entry_amount_usdt"] > 0
    assert "SELLABILITY_NOT_OK" not in sized.get("blockers", [])


def test_hot_observation_uses_latest_price_transition(history, monkeypatch):
    monkeypatch.setattr(
        "app.risk.paper_position_sizing._empirical_outcome_calibration",
        lambda **_: dict(
            gap_multiplier=None,
            cost_uncertainty_fraction=None,
            account_risk_budget_fraction=None,
            gap_samples=0,
            cost_samples=0,
            account_risk_samples=0,
        ),
    )
    p = plan(observe([1.0, 1.0, 1.06]))
    # Reproduce the real runtime blocker set seen in production while
    # preserving the already-qualified HOT plan.
    p["expected"]["known_net_edge_fraction"] = 0.0
    p["expected"]["full_net_edge_fraction"] = None
    p["cost_model"]["cost_complete"] = False
    p["capital"]["liquidity_capacity_source"] = "UNKNOWN"
    sized = calculate_paper_position_size(
        mathematical_plan=p,
        available_capital_usdt=10000.0,
    )
    assert sized["entry_amount_usdt"] > 0.0
    assert sized["sizing_reason"] == "PAPER_HOT_OBSERVATION_BOOTSTRAP"
    assert sized["observation_fraction"] > 0.0


def test_hot_observation_bootstrap_sizes_from_available_balance(history, monkeypatch):
    monkeypatch.setattr(
        "app.risk.paper_position_sizing._empirical_outcome_calibration",
        lambda **_: dict(
            gap_multiplier=None,
            cost_uncertainty_fraction=None,
            account_risk_budget_fraction=None,
            gap_samples=0,
            cost_samples=0,
            account_risk_samples=0,
        ),
    )
    p = plan(observe([1.0, 1.04, 1.06]))
    p["expected"]["known_net_edge_fraction"] = 0.0
    p["expected"]["full_net_edge_fraction"] = None
    p["cost_model"]["cost_complete"] = False
    sized = calculate_paper_position_size(
        mathematical_plan=p,
        available_capital_usdt=5000.0,
    )
    assert sized["entry_amount_usdt"] > 1.0
    assert sized["entry_amount_usdt"] <= 5000.0
    assert sized["capital_before_usdt"] == 5000.0
    assert sized["sizing_reason"] == "PAPER_HOT_OBSERVATION_BOOTSTRAP"
    assert sized["paper_hot_observation_bootstrap"] is True
    assert sized["immediate_entry_allowed"] is True


@pytest.mark.parametrize("quote", [WBNB, None, "0xunknown"])
def test_runtime_non_usdt_never_reaches_planning(monkeypatch, quote):
    pipeline = engine.PipelineEngine.__new__(engine.PipelineEngine)
    monkeypatch.setattr(engine, "token_analyze", lambda _: {"data": {}})
    monkeypatch.setattr(engine, "pair_analyze", lambda _: {
        "data": {"exists": True, "quote_ok": True, "pair": "0xpool"}})
    monkeypatch.setattr(engine, "risk_analyze", lambda _: {"data": {}})
    monkeypatch.setattr(engine, "sellability_analyze", lambda *a, **k: {
        "success": True, "data": {"sellable": True}})
    monkeypatch.setattr(engine, "_strategy", SimpleNamespace(evaluate=lambda *a: {
        "data": {"decision": "PAPER_BUY"}}))
    monkeypatch.setattr(engine, "_risk_gate", SimpleNamespace(evaluate=lambda *a: {
        "hard_block": False, "hard_block_reasons": []}))

    def forbidden_plan(**kwargs):
        pytest.fail("Non-USDT candidate reached mathematical planning")

    monkeypatch.setattr(engine, "build_trade_plan", forbidden_plan)
    result = pipeline.run("0xtoken", market_context={"candidate_quote_token": quote})
    assert result["data"]["paper"] == {"action": "SKIP", "reason": "NON_USDT_QUOTE"}
