import math
import sqlite3

from app.risk import paper_position_sizing as sizing


def _bootstrap_plan():
    risk_log_distance = 0.20
    return {
        "paper_eligible": True,
        "capital": {
            "entry_amount_usdt": 1000.0,
            "available_usdt": 10000.0,
            "safe_quote_reserve_usd": 5000.0,
            "liquidity_capacity_source": "VERIFIED_LP_PROTECTION",
        },
        "expected": {
            "known_net_edge_fraction": 0.10,
            "full_net_edge_fraction": 0.10,
        },
        "cost_model": {
            "cost_complete": True,
        },
        "market_statistics": {
            "risk_log_distance": risk_log_distance,
        },
        "entry": {
            "price": 1.0,
        },
        "sl": {
            "initial_price": math.exp(-risk_log_distance),
        },
        "position": {},
    }


def test_registry_integrity_failure_cannot_bootstrap_paper_entry(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "existing.db"
    sqlite3.connect(db_path).close()

    monkeypatch.setattr(
        sizing,
        "PAPER_OUTCOME_EXCLUSIONS_PATH",
        tmp_path / "missing-registry.json",
    )

    result = sizing.calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(),
        available_capital_usdt=10000.0,
        db_path=str(db_path),
    )

    assert result["entry_amount_usdt"] == 0.0
    assert result["risk_amount_usdt"] == 0.0
    assert (
        "OUTCOME_EXCLUSION_REGISTRY_INVALID"
        in result["blockers"]
    )
    assert result.get("paper_calibration_bootstrap") is not True
