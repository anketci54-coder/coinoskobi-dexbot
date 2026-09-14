import json
import math
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


def _valid_exclusion():
    return {
        "source_table": "paper_trades",
        "position_id": 37,
        "created_at": "2026-09-13T15:18:35.118255+00:00",
        "closed_at": "2026-09-13T16:25:18.506054+00:00",
        "reason": "BUG_CONTAMINATED_RUNTIME_LIFECYCLE_STARVATION_PR147",
    }


def _write_registry(path, exclusions):
    path.write_text(
        json.dumps({
            "version": 1,
            "exclusions": exclusions,
        }),
        encoding="utf-8",
    )


def _calibration(db_path, exclusion_path, monkeypatch):
    monkeypatch.setattr(
        sizing,
        "PAPER_OUTCOME_EXCLUSIONS_PATH",
        exclusion_path,
    )
    return sizing._empirical_outcome_calibration(
        str(db_path)
    )


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


def test_contaminated_outcome_is_excluded_only_from_calibration(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    db = _build_db(db_path)
    _write_registry(
        exclusion_path,
        [_valid_exclusion()],
    )

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
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


def test_exclusion_requires_exact_incident_fingerprint(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    db = _build_db(db_path)
    db.close()

    exclusion = _valid_exclusion()
    exclusion["created_at"] = "2099-01-01T00:00:00+00:00"
    _write_registry(
        exclusion_path,
        [exclusion],
    )

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
    )

    assert calibration["excluded_samples"] == 0
    assert calibration["gap_samples"] == 2
    assert calibration["gap_multiplier"] == pytest.approx(2.0)
    assert calibration["account_risk_samples"] == 2
    assert calibration["account_risk_budget_usdt"] == pytest.approx(30.0)


def test_missing_registry_fails_calibration_closed(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "missing.json"

    db = _build_db(db_path)
    db.close()

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_EXCLUSION_REGISTRY_INVALID"
    assert calibration["gap_samples"] == 0
    assert calibration["account_risk_samples"] == 0


def test_invalid_json_registry_fails_calibration_closed(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    db = _build_db(db_path)
    db.close()
    exclusion_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_EXCLUSION_REGISTRY_INVALID"
    assert calibration["gap_samples"] == 0
    assert calibration["account_risk_samples"] == 0


def test_wrong_registry_shape_fails_calibration_closed(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    db = _build_db(db_path)
    db.close()
    exclusion_path.write_text(
        json.dumps({
            "version": 1,
            "exclusions": {},
        }),
        encoding="utf-8",
    )

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_EXCLUSION_REGISTRY_INVALID"


@pytest.mark.parametrize(
    "missing_key",
    [
        "source_table",
        "position_id",
        "created_at",
        "closed_at",
    ],
)
def test_incomplete_fingerprint_fails_calibration_closed(
    tmp_path,
    monkeypatch,
    missing_key,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    db = _build_db(db_path)
    db.close()

    exclusion = _valid_exclusion()
    exclusion.pop(missing_key)
    _write_registry(
        exclusion_path,
        [exclusion],
    )

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_EXCLUSION_REGISTRY_INVALID"
    assert calibration["gap_samples"] == 0
    assert calibration["account_risk_samples"] == 0


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("source_table", 123),
        ("created_at", 1789320000),
        ("created_at", {"value": "bad"}),
        ("closed_at", 1789321000.5),
        ("closed_at", ["bad"]),
        ("position_id", True),
        ("position_id", 37.8),
        ("position_id", "37"),
    ],
)
def test_malformed_fingerprint_value_types_fail_closed(
    tmp_path,
    monkeypatch,
    key,
    value,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    sqlite3.connect(db_path).close()
    exclusion = _valid_exclusion()
    exclusion[key] = value
    _write_registry(exclusion_path, [exclusion])

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_EXCLUSION_REGISTRY_INVALID"
    assert calibration["gap_samples"] == 0
    assert calibration["account_risk_samples"] == 0


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("created_at", "not-a-date"),
        ("closed_at", "also-not-a-date"),
        ("created_at", "2026-09-13T15:18:35.118255"),
        ("closed_at", "2026-09-13T16:25:18.506054"),
    ],
)
def test_invalid_or_naive_fingerprint_timestamps_fail_closed(
    tmp_path,
    monkeypatch,
    key,
    value,
):
    db_path = tmp_path / "paper.db"
    exclusion_path = tmp_path / "exclusions.json"

    sqlite3.connect(db_path).close()
    exclusion = _valid_exclusion()
    exclusion[key] = value
    _write_registry(exclusion_path, [exclusion])

    calibration = _calibration(
        db_path,
        exclusion_path,
        monkeypatch,
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_EXCLUSION_REGISTRY_INVALID"
    assert calibration["gap_samples"] == 0
    assert calibration["account_risk_samples"] == 0


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


def test_registry_integrity_is_checked_before_missing_database_bootstrap(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "not-created.db"

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
