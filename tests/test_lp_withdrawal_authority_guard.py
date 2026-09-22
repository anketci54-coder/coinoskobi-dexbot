import app.risk.paper_position_sizing as sizing


def _calibration():
    return {
        "ready": True,
        "reason": "EMPIRICAL_OUTCOME_CALIBRATION",
        "gap_multiplier": 1.0,
        "gap_median": 1.0,
        "gap_statistic": "MAX_OBSERVED",
        "cost_uncertainty_fraction": 0.0,
        "account_risk_budget_fraction": 0.01,
        "account_risk_statistic": "MEDIAN_REALIZED_LOSS_USDT",
        "account_risk_samples": 1,
        "gap_samples": 1,
        "cost_samples": 1,
    }


def _plan(source):
    return {
        "sellability_status": "SELLABILITY_OK",
        "statistics": {"second_moment": 0.04, "tail_risk_fraction": 0.1},
        "capital": {
            "entry_amount_usdt": 100.0,
            "available_usdt": 1000.0,
            "safe_quote_reserve_usd": 10000.0,
            "liquidity_capacity_source": source,
        },
        "sl": {
            "risk_log_distance": 0.10,
        },
        "expected": {
            "full_net_edge_fraction": 0.20,
            "known_net_edge_fraction": 0.20,
        },
        "cost_model": {
            "cost_complete": True,
        },
    }


def test_empirical_reserve_floor_cannot_grant_paper_capital(monkeypatch):
    monkeypatch.setattr(
        sizing,
        "_empirical_outcome_calibration",
        lambda db_path: _calibration(),
    )

    result = sizing.calculate_paper_position_size(
        mathematical_plan=_plan("EMPIRICAL_RESERVE_FLOOR"),
        available_capital_usdt=1000.0,
    )

    assert result["entry_amount_usdt"] == 0.0
    assert result["risk_amount_usdt"] == 0.0
    assert (
        "EMPIRICAL_EXIT_EVIDENCE_INVALID"
        in result["blockers"]
    )


def test_verified_lp_protection_preserves_paper_sizing(monkeypatch):
    monkeypatch.setattr(
        sizing,
        "_empirical_outcome_calibration",
        lambda db_path: _calibration(),
    )

    result = sizing.calculate_paper_position_size(
        mathematical_plan=_plan("VERIFIED_LP_PROTECTION"),
        available_capital_usdt=1000.0,
    )

    assert result["entry_amount_usdt"] > 0.0
    assert result["risk_amount_usdt"] > 0.0
    assert result["risk_amount_usdt"] <= 10.0
    assert result["account_risk_budget_usdt"] == 10.0
    assert result["blockers"] == []


def test_hot_empirical_reserve_floor_sizes_for_total_loss_without_lp_protection(monkeypatch):
    monkeypatch.setattr(
        sizing,
        "_empirical_outcome_calibration",
        lambda db_path: _calibration(),
    )

    plan = _plan("EMPIRICAL_RESERVE_FLOOR")
    plan["paper_eligible"] = True
    plan["capital"].update({
        "reserve_observation_count": 4,
        "observed_min_quote_reserve_usd": 10000.0,
    })
    plan["entry"] = {"price": 1.0}
    plan["sl"]["initial_price"] = 0.90
    plan["position"] = {}
    plan["market_context"] = {
        "opportunity": {
            "state": "HOT",
            "catastrophic_reserve_collapse": False,
        }
    }

    result = sizing.calculate_paper_position_size(
        mathematical_plan=plan,
        available_capital_usdt=1000.0,
    )

    assert result["entry_amount_usdt"] > 0.0
    assert result["risk_amount_usdt"] == result["entry_amount_usdt"]
    assert result["tail_loss_fraction"] == 1.0
    assert result["liquidity_protection_unverified"] is True
    assert result.get("paper_calibration_bootstrap") is not True
