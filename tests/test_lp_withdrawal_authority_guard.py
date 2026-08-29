import app.risk.paper_position_sizing as sizing


def _calibration():
    return {
        "ready": True,
        "reason": "EMPIRICAL_OUTCOME_CALIBRATION",
        "gap_multiplier": 1.0,
        "gap_median": 1.0,
        "gap_statistic": "MAX_OBSERVED",
        "cost_uncertainty_fraction": 0.0,
        "gap_samples": 1,
        "cost_samples": 1,
    }


def _plan(source):
    return {
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
        "LP_WITHDRAWAL_PROTECTION_UNVERIFIED"
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
    assert result["blockers"] == []
