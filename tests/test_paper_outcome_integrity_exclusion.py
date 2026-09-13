import json
import sqlite3

import pytest

from app.risk import paper_position_sizing as sizing


def _build_db(path):
    db = sqlite3.connect(path)
    db.execute(
        """
        CREATE TABLE paper_trades (
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            closed_at TEXT,
            status TEXT,
            entry_price REAL,
            current_price REAL,
            exit_price REAL,
            entry_amount_usdt REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT,
            gross_pnl_usdt REAL,
            net_pnl_usdt REAL,
            net_pnl REAL,
            paper_account_version TEXT,
            realized_pnl_usdt REAL DEFAULT 0,
            remaining_cost_basis_usdt REAL
        )
        """
    )

    plan = json.dumps({
        "entry": {
            "band_low": 9.0,
        },
    })
    state = json.dumps({
        "last_stop": 9.0,
    })

    db.execute(
        """
        INSERT INTO paper_trades(
            id, created_at, closed_at, status,
            entry_price, current_price, exit_price,
            entry_amount_usdt,
            mathematical_plan_json, math_state_json,
            gross_pnl_usdt, net_pnl_usdt, net_pnl,
            paper_account_version
        ) VALUES (?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            37,
            "2026-09-13T15:18:35.118255+00:00",
            "2026-09-13T16:25:18.506054+00:00",
            10.0,
            8.0,
            8.0,
            100.0,
            plan,
            state,
            -20.0,
            -50.0,
            -50.0,
            "PAPER_10K_V2",
        ),
    )

    db.execute(
        """
        INSERT INTO paper_trades(
            id, created_at, closed_at, status,
            entry_price, current_price, exit_price,
            entry_amount_usdt,
            mathematical_plan_json, math_state_json,
            gross_pnl_usdt, net_pnl_usdt, net_pnl,
            paper_account_version
        ) VALUES (?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            38,
            "2026-09-13T17:00:00+00:00",
            "2026-09-13T17:05:00+00:00",
            10.0,
            9.0,
            9.0,
            100.0,
            plan,
            state,
            -10.0,
            -10.0,
            -10.0,
            "PAPER_10K_V2",
        ),
    )

    db.commit()
    return db


def _write_exclusions(path, *, created_at=None):
    path.write_text(
        json.dumps({
            "version": 1,
            "exclusions": [
                {
                    "source_table": "paper_trades",
                    "position_id": 37,
                    "created_at": (
                        created_at
                        or "2026-09-13T15:18:35.118255+00:00"
                    ),
                    "closed_at": "2026-09-13T16:25:18.506054+00:00",
                    "reason": "BUG_CONTAMINATED_RUNTIME_LIFECYCLE_STARVATION_PR147",
                }
            ],
        }),
        encoding="utf-8",
    )


def test_contaminated_outcome_is_excluded_only_from_calibration(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    db = _build_db(db_path)
    _write_exclusions(exclusion_path)

    monkeypatch.setattr(
        sizing,
        "PAPER_OUTCOME_EXCLUSIONS_PATH",
        exclusion_path,
    )

    calibration = sizing._empirical_outcome_calibration(
        str(db_path)
    )

    assert calibration["excluded_samples"] == 1
    assert calibration["gap_samples"] == 1
    assert calibration["gap_multiplier"] == pytest.approx(1.0)
    assert calibration["account_risk_samples"] == 1
    assert calibration["account_risk_budget_usdt"] == pytest.approx(10.0)

    capital = sizing.paper_available_capital_usdt(
        db,
        10_000.0,
    )
    assert capital == pytest.approx(9_940.0)

    db.close()


def test_exclusion_requires_full_incident_fingerprint(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    db = _build_db(db_path)
    db.close()

    _write_exclusions(
        exclusion_path,
        created_at="2099-01-01T00:00:00+00:00",
    )

    monkeypatch.setattr(
        sizing,
        "PAPER_OUTCOME_EXCLUSIONS_PATH",
        exclusion_path,
    )

    calibration = sizing._empirical_outcome_calibration(
        str(db_path)
    )

    assert calibration["excluded_samples"] == 0
    assert calibration["gap_samples"] == 2
    assert calibration["gap_multiplier"] == pytest.approx(2.0)
    assert calibration["account_risk_samples"] == 2
    assert calibration["account_risk_budget_usdt"] == pytest.approx(30.0)
