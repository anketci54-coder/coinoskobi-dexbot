import json
import math
import sqlite3

from app.risk.paper_position_sizing import (
    calculate_paper_position_size,
)


def _plan():
    return {
        "capital": {
            "entry_amount_usdt": 1000.0,
            "available_usdt": 10000.0,
            "safe_quote_reserve_usd": 1000000.0,
        },
        "expected": {
            "known_net_edge_fraction": 0.50,
            "full_net_edge_fraction": 0.50,
        },
        "cost_model": {
            "cost_complete": True,
        },
        "market_statistics": {
            "risk_log_distance": 0.05,
        },
    }


def test_catastrophic_exit_overrides_stale_current_price(tmp_path):
    db_path = tmp_path / "paper.db"
    db = sqlite3.connect(db_path)

    db.execute(
        """
        CREATE TABLE paper_trades (
            status TEXT,
            entry_price REAL,
            current_price REAL,
            exit_price REAL,
            entry_amount_usdt REAL,
            net_pnl REAL,
            gross_pnl_usdt REAL,
            net_pnl_usdt REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT
        )
        """
    )

    db.execute(
        """
        INSERT INTO paper_trades VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            "CLOSED",
            100.0,
            99.0,
            0.0001,
            100.0,
            -100.0,
            -100.0,
            -100.0,
            json.dumps({
                "entry": {
                    "band_low": 95.0,
                }
            }),
            json.dumps({
                "last_stop": 95.0,
            }),
        ),
    )

    db.commit()
    db.close()

    result = calculate_paper_position_size(
        mathematical_plan=_plan(),
        available_capital_usdt=10000.0,
        db_path=str(db_path),
    )

    assert math.isclose(
        result["gap_multiplier"],
        20.0,
        rel_tol=1e-3,
    )

    assert math.isclose(
        result["tail_loss_fraction"],
        1.0 - math.exp(-0.05),
        rel_tol=1e-9,
    ) is False

    assert result["tail_loss_fraction"] > 0.95

    original_stop_budget = (
        1000.0
        * (
            1.0
            - math.exp(-0.05)
        )
    )

    assert (
        result["entry_amount_usdt"]
        <= original_stop_budget + 1e-9
    )

    assert (
        result["risk_amount_usdt"]
        <= original_stop_budget + 1e-9
    )
