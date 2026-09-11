from app.risk.paper_position_sizing import calculate_paper_position_size


def _bootstrap_plan(*, known_edge=0.10, paper_eligible=True):
    return {
        "paper_eligible": paper_eligible,
        "capital": {
            "entry_amount_usdt": 1000.0,
            "available_usdt": 10000.0,
            "safe_quote_reserve_usd": 5000.0,
            "liquidity_capacity_source": "VERIFIED_LP_PROTECTION",
        },
        "expected": {
            "known_net_edge_fraction": known_edge,
            "full_net_edge_fraction": None,
        },
        "cost_model": {
            "cost_complete": False,
        },
        "market_statistics": {
            "risk_log_distance": 0.20,
        },
        "entry": {"price": 1.0},
        "sl": {"initial_price": 0.80},
        "position": {},
    }


def test_paper_calibration_bootstrap_uses_plan_derived_amount(tmp_path):
    result = calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(),
        available_capital_usdt=10000.0,
        db_path=str(tmp_path / "missing.db"),
    )

    assert result["entry_amount_usdt"] > 0
    assert result["entry_amount_usdt"] <= 1000.0
    assert result["sizing_reason"] == "PAPER_CALIBRATION_BOOTSTRAP"
    assert result["paper_calibration_bootstrap"] is True
    assert result["blockers"] == []


def test_paper_calibration_bootstrap_never_overrides_negative_edge(tmp_path):
    result = calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(known_edge=-0.01),
        available_capital_usdt=10000.0,
        db_path=str(tmp_path / "missing.db"),
    )

    assert result["entry_amount_usdt"] == 0.0
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
