import math

import pytest

from app.risk.paper_position_sizing import calculate_paper_position_size


def _bootstrap_plan(
    *,
    known_edge=0.10,
    full_edge=None,
    cost_complete=True,
    paper_eligible=True,
    entry_amount_usdt=1000.0,
    available_usdt=10000.0,
    safe_quote_reserve_usd=5000.0,
    risk_log_distance=0.20,
):
    if full_edge is None and cost_complete:
        full_edge = known_edge

    return {
        "paper_eligible": paper_eligible,
        "capital": {
            "entry_amount_usdt": entry_amount_usdt,
            "available_usdt": available_usdt,
            "safe_quote_reserve_usd": safe_quote_reserve_usd,
            "liquidity_capacity_source": "VERIFIED_LP_PROTECTION",
        },
        "expected": {
            "known_net_edge_fraction": known_edge,
            "full_net_edge_fraction": full_edge,
        },
        "cost_model": {
            "cost_complete": cost_complete,
        },
        "market_statistics": {
            "risk_log_distance": risk_log_distance,
        },
        "entry": {"price": 1.0},
        "sl": {"initial_price": math.exp(-risk_log_distance)},
        "position": {},
    }


def test_paper_calibration_bootstrap_is_bounded_by_plan_stop_risk(tmp_path):
    result = calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(),
        available_capital_usdt=10000.0,
        db_path=str(tmp_path / "missing.db"),
    )

    stop_loss_fraction = 1.0 - math.exp(-0.20)
    expected_budget = 1000.0 * stop_loss_fraction

    assert result["entry_amount_usdt"] == pytest.approx(expected_budget)
    assert result["risk_amount_usdt"] == pytest.approx(expected_budget)
    assert result["bootstrap_risk_budget_usdt"] == pytest.approx(expected_budget)
    assert result["bootstrap_tail_loss_fraction"] == 1.0
    assert result["sizing_reason"] == "PAPER_CALIBRATION_BOOTSTRAP"
    assert result["sizing_model"] == "PAPER_CALIBRATION_BOOTSTRAP_V2"
    assert result["paper_calibration_bootstrap"] is True
    assert result["blockers"] == []


def test_hotdog_shape_cannot_bootstrap_sixty_percent_of_account(tmp_path):
    raw_amount = 5974.6173336504025
    available = 9372.54877751162
    risk_log_distance = 0.07563632051428575

    result = calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(
            known_edge=0.23102489735017798,
            entry_amount_usdt=raw_amount,
            available_usdt=available,
            safe_quote_reserve_usd=25861.356945413227,
            risk_log_distance=risk_log_distance,
        ),
        available_capital_usdt=available,
        db_path=str(tmp_path / "missing.db"),
    )

    expected_budget = raw_amount * (
        1.0 - math.exp(-risk_log_distance)
    )

    assert result["entry_amount_usdt"] == pytest.approx(expected_budget)
    assert result["entry_amount_usdt"] < raw_amount
    assert result["position_size_pct"] == pytest.approx(
        100.0 * expected_budget / available
    )
    assert result["position_size_pct"] < 5.0
    assert result["risk_amount_usdt"] == pytest.approx(expected_budget)
    assert result["bootstrap_tail_loss_fraction"] == 1.0


def test_paper_calibration_bootstrap_never_overrides_negative_edge(tmp_path):
    result = calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(known_edge=-0.01),
        available_capital_usdt=10000.0,
        db_path=str(tmp_path / "missing.db"),
    )

    assert result["entry_amount_usdt"] == 0.0
    assert "NET_EDGE_NOT_POSITIVE" in result["blockers"]
    assert result.get("paper_calibration_bootstrap") is not True


def test_paper_calibration_bootstrap_requires_complete_cost_edge(tmp_path):
    result = calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(
            known_edge=0.10,
            full_edge=None,
            cost_complete=False,
        ),
        available_capital_usdt=10000.0,
        db_path=str(tmp_path / "missing.db"),
    )

    assert result["entry_amount_usdt"] == 0.0
    assert "COST_UNCERTAINTY_UNOBSERVED" in result["blockers"]
    assert "NET_EDGE_NOT_POSITIVE" in result["blockers"]
    assert result.get("paper_calibration_bootstrap") is not True


def test_paper_calibration_bootstrap_requires_paper_eligibility(tmp_path):
    result = calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(paper_eligible=False),
        available_capital_usdt=10000.0,
        db_path=str(tmp_path / "missing.db"),
    )

    assert result["entry_amount_usdt"] == 0.0
    assert "GAP_RISK_UNOBSERVED" in result["blockers"]
    assert result.get("paper_calibration_bootstrap") is not True
