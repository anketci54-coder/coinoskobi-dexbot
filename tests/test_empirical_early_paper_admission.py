import pytest

from app.risk.paper_position_sizing import calculate_paper_position_size
from app.strategy.mathematical_trade_plan import build_trade_plan


def _quality():
    return {
        "buy_sell_count_ratio": 1.34,
        "volume_turnover": 0.12,
        "buys": 11,
        "sells": 8,
        "transaction_count": 19,
        "market_evidence_ready": True,
        "suspicious_volume": False,
        "participation_state": "BROAD",
        "liquidity_state": "STABLE",
    }


def _plan(quality, **overrides):
    args = dict(
        entry_price=1.01,
        available_capital_usdt=10000,
        price_series=[0.99, 1.0, 1.01],
        quote_reserve_usd=50000,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        sellability_data=dict(buy_tax=0, sell_tax=0, buy_gas=0, sell_gas=0),
        exit_evidence=dict(route_friction_fraction=0, gas_price_wei=0, wbnb_usd_estimate=600),
        market_context={"runtime_intelligence": {}, "market_quality": quality},
    )
    args.update(overrides)
    return build_trade_plan(**args)


@pytest.fixture
def calibrated(monkeypatch):
    monkeypatch.setattr("app.risk.paper_position_sizing._empirical_outcome_calibration",
        lambda *args, **kwargs: dict(ready=True, reason="EMPIRICAL_OUTCOME_CALIBRATION",
            gap_multiplier=1.0, cost_uncertainty_fraction=0.0,
            account_risk_budget_fraction=0.01, gap_samples=1, cost_samples=1,
            account_risk_samples=1))


def test_boundary_admission_reaches_bounded_paper_sizing(tmp_path, calibrated):
    plan = _plan(_quality())
    assert plan["paper_eligible"] is True
    assert plan["vur_kac_entry"]["ready"] is False
    assert plan["paper_admission"]["mode"] == "EARLY_EMPIRICAL"
    assert plan["paper_admission"]["early_paper_admission"] is True
    assert set(plan["paper_admission"]["bypassed_soft_blockers"]) == {
        "VUR_KAC_ENTRY_NOT_READY", "VUR_KAC_FLOW_EVIDENCE_NOT_READY",
    }
    assert plan["blockers"] == []
    for key in ("live_eligible", "wallet_authority", "execution_authority"):
        assert plan[key] is False
    result = calculate_paper_position_size(
        mathematical_plan=plan, db_path=str(tmp_path / "missing.db"),
    )
    assert 0 < result["entry_amount_usdt"] <= plan["capital"]["entry_amount_usdt"]
    assert result["immediate_entry_allowed"] is True


def test_missing_cost_calibration_still_blocks_sizing(tmp_path):
    result = calculate_paper_position_size(
        mathematical_plan=_plan(_quality()), db_path=str(tmp_path / "missing.db"))
    assert result["entry_amount_usdt"] == 0
    assert "COST_UNCERTAINTY_UNOBSERVED" in result["blockers"]


@pytest.mark.parametrize("mutation,blocker", [
    ({"hard_block": True}, "HARD_BLOCK"),
    ({"sellability_status": "SELLABILITY_FAIL"}, "SELLABILITY_NOT_OK"),
    ({"blockers": ["FUTURE_HARD_SAFETY"]}, "PLAN_BLOCKED"),
])
def test_sizing_rechecks_safety(calibrated, mutation, blocker):
    plan = _plan(_quality())
    plan.update(mutation)
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] == 0
    assert blocker in result["blockers"]


def test_early_lane_cannot_bypass_chase_limit(calibrated):
    plan = _plan(_quality(), entry_price=1.05, price_series=[1, 1.02, 1.05])
    assert plan["paper_eligible"] is True
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] == 0
    assert "ENTRY_ABOVE_CHASE_LIMIT" in result["blockers"]


@pytest.mark.parametrize("field,value,blocker", [
    ("expected", {"known_net_edge_fraction": -0.01}, "NET_EDGE_NOT_POSITIVE"),
    ("capital", {"entry_amount_usdt": 0}, "PLAN_AMOUNT_ZERO"),
    ("capital", {"liquidity_capacity_source": "EMPIRICAL_RESERVE_FLOOR"},
        "EMPIRICAL_EXIT_EVIDENCE_INVALID"),
])
def test_early_sizing_preserves_economic_and_lp_guards(calibrated, field, value, blocker):
    plan = _plan(_quality())
    plan[field].update(value)
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] == 0
    assert blocker in result["blockers"]


def test_runtime_nested_quality_is_consumed():
    plan = _plan(None, market_context={"runtime_intelligence": {"market_quality": _quality()}})
    assert plan["paper_admission"]["mode"] == "EARLY_EMPIRICAL"


def test_unknown_readiness_reason_fails_closed(monkeypatch):
    monkeypatch.setattr("app.strategy.mathematical_trade_plan.vur_kac_entry_admission_state",
        lambda **kwargs: {"enforced": True, "ready": False, "reason": "FUTURE_HARD_SAFETY"})
    plan = _plan(_quality())
    assert plan["paper_eligible"] is False
    assert plan["paper_admission"]["bypassed_soft_blockers"] == []


@pytest.mark.parametrize("key,value", [
    ("buy_sell_count_ratio", 1.339), ("volume_turnover", 0.121), ("buys", 12),
])
def test_each_empirical_condition_is_required(key, value):
    quality = _quality()
    quality[key] = value
    assert _plan(quality)["paper_eligible"] is False


@pytest.mark.parametrize("key", ["buy_sell_count_ratio", "volume_turnover", "buys"])
@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), "invalid"])
def test_invalid_evidence_fails_closed(key, value):
    quality = _quality()
    quality[key] = value
    assert _plan(quality)["paper_eligible"] is False
    del quality[key]
    assert _plan(quality)["paper_eligible"] is False


@pytest.mark.parametrize("quality", [None, {}, []])
def test_missing_quality_fails_closed(quality):
    assert _plan(quality)["paper_eligible"] is False


@pytest.mark.parametrize("overrides", [
    {"hard_block": True},
    {"sellability_status": "SELLABILITY_FAIL"},
    {"sellability_status": "SELLABILITY_SKIPPED"},
    {"sellability_status": None},
    {"available_capital_usdt": 0},
    {"quote_reserve_usd": 0},
    {"lp_protected_fraction": None},
    {"price_series": [1.03, 1.02, 1.01]},
    {"price_series": [1.01, 1.01, 1.01]},
])
def test_safety_and_economics_are_never_bypassed(overrides):
    plan = _plan(_quality(), **overrides)
    assert plan["paper_eligible"] is False
    assert plan["paper_admission"]["mode"] == "BLOCKED"
    assert plan["paper_admission"]["bypassed_soft_blockers"] == []


@pytest.mark.parametrize("key,value,blocker", [
    ("suspicious_volume", True, "SUSPICIOUS_VOLUME"),
    ("participation_state", "CONCENTRATED", "PARTICIPATION_CONCENTRATED"),
    ("liquidity_state", "NO_LIQUIDITY", "MARKET_QUALITY_NO_LIQUIDITY"),
    ("liquidity_state", "DETERIORATING_FAST", "MARKET_QUALITY_LIQUIDITY_DETERIORATING_FAST"),
])
def test_adverse_quality_is_never_bypassed(key, value, blocker):
    quality = _quality()
    quality[key] = value
    plan = _plan(quality)
    assert plan["paper_eligible"] is False
    assert blocker in plan["blockers"]
    assert plan["paper_admission"]["bypassed_soft_blockers"] == []


def test_full_evidence_takes_precedence():
    plan = _plan(_quality(), entry_price=1.05, price_series=[1, 1.02, 1.05],
        market_context={"runtime_intelligence": {}, "market_quality": _quality(),
            "flow_intelligence": {"buy_flow": 8, "sell_flow": 2,
                "prev_spread": 3, "prev_velocity": 1, "freshness": "FRESH", "coverage": 1.0}})
    assert plan["paper_eligible"] is True
    assert plan["vur_kac_entry"]["ready"] is True
    assert plan["paper_admission"]["mode"] == "FULL_EVIDENCE"
    assert plan["paper_admission"]["bypassed_soft_blockers"] == []
