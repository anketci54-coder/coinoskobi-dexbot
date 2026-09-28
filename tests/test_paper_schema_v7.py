"""Forward-only schema compatibility; all writes target disposable test DBs."""
import json
import sqlite3
from pathlib import Path

import pytest

from app.paper.schema import ensure_paper_schema
from tests.paper_calibration_fixtures import execution, opening


V6_SCHEMA = Path(__file__).with_name("fixtures") / "paper_schema_v6.sql"
QUARANTINES = """
CREATE TABLE paper_position_quarantines (
    position_id INTEGER PRIMARY KEY,
    quarantined_at TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    previous_run_id INTEGER,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY(position_id) REFERENCES paper_trades(id)
)
"""


def _insert(db, table, values):
    db.execute(
        f"INSERT INTO {table} ({','.join(values)}) "
        f"VALUES ({','.join('?' for _ in values)})",
        tuple(values.values()),
    )


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "paper.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(V6_SCHEMA.read_text())
        _insert(db, "paper_runs", {
            "id": 2, "run_key": "existing-run", "started_at": 1790072283,
            "starting_capital_usdt": 10000, "start_trade_id": 0,
            "start_realization_id": 0, "start_candidate_id": 9,
            "status": "ACTIVE", "metadata_json": '{"preserve":true}',
        })
        for position_id, status in ((1, "CLOSED"), (2, "OPEN")):
            _insert(db, "paper_trades", {
                "id": position_id, "token": f"token-{position_id}", "pool": "pool",
                "created_at": "2026-09-27T10:00:00+00:00",
                "closed_at": "2026-09-27T11:00:00+00:00" if position_id == 1 else None,
                "status": status, "entry_price": 1.25, "current_price": 0.9,
                "exit_price": 0.9 if position_id == 1 else None,
                "highest_price": 1.4, "lowest_price": 0.8,
                "amount_bnb": 0, "entry_amount_usdt": 125.5,
                "risk_amount_usdt": 20, "capital_before_usdt": 9000.75,
                "capital_after_entry_usdt": 8875.25,
                "token_amount": 0 if position_id == 1 else 75.25,
                "initial_token_amount": 100,
                "remaining_cost_basis_usdt": 0 if position_id == 1 else 94.5,
                "gross_pnl": -35.5, "net_pnl": -36.25,
                "gross_pnl_usdt": -35.5, "net_pnl_usdt": -36.25,
                "realized_gross_proceeds_usdt": 90,
                "realized_proceeds_usdt": 89.25, "realized_pnl_usdt": -36.25,
                "paper_account_version": "PAPER_10K_V2",
                "trade_policy": "NORMAL", "trade_type": "NORMAL", "control_mode": "AUTO",
                "paper_run_id": 2 if position_id == 1 else None,
                "opening_context_json": json.dumps(opening(1.25)) if position_id == 1 else None,
                "closing_execution_json": json.dumps(execution("SELL")) if position_id == 1 else None,
                "mathematical_plan_json": '{"historical_plan":true}',
                "math_state_json": '{"historical_state":true}',
            })
        _insert(db, "paper_realizations", {
            "position_id": 1, "stage": "TP1", "observed_at": "2026-09-27T10:30:00+00:00",
            "price": 1.4, "token_amount": 10, "close_fraction": 0.1,
            "gross_proceeds_usdt": 14, "net_proceeds_usdt": 13.75,
            "sold_cost_basis_usdt": 12.55, "realized_pnl_usdt": 1.2,
            "execution_evidence_json": json.dumps(execution("SELL", stage="NORMAL_TP1", fraction=0.1)),
        })
    yield path


def _rows(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return {table: db.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() for table in tables}


def _schema(db):
    return db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()


def _assert_preserved(db, before):
    after = _rows(db)
    for table, rows in before.items():
        assert after[table] == rows, table
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_schema6_to_schema7_preserves_history_and_proof(database):
    with sqlite3.connect(database) as db:
        before, schema_before = _rows(db), _schema(db)
        assert db.execute("PRAGMA user_version").fetchone() == (6,)
        result = ensure_paper_schema(db)
        assert result["schema_version"] == 7
        assert db.execute("PRAGMA user_version").fetchone() == (7,)
        assert db.execute("SELECT * FROM paper_position_quarantines").fetchall() == []
        assert set(schema_before) <= set(_schema(db))
        _assert_preserved(db, before)
        assert db.execute("SELECT paper_run_id, opening_context_json, closing_execution_json "
                          "FROM paper_trades WHERE id=2").fetchone() == (None, None, None)
        # The database-enforced single-OPEN gate remains active after migration.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO paper_trades(token,status) VALUES ('TOKEN-2','OPEN')")


@pytest.mark.parametrize("version", [7, 8])
def test_existing_schema7_and_newer_preserve_all_rows(database, version):
    # Build the existing v7 contract independently of the initializer under test.
    with sqlite3.connect(database) as db:
        db.execute(QUARANTINES)
        db.execute("UPDATE paper_trades SET status='QUARANTINED' WHERE id=2")
        db.execute("INSERT INTO paper_position_quarantines VALUES "
                   "(2,'2026-09-27T12:00:00+00:00','OPEN','legacy',NULL,'{}')")
        db.execute(f"PRAGMA user_version={version}")
    with sqlite3.connect(database) as db:
        before, schema_before = _rows(db), _schema(db)
        if version == 8:
            with pytest.raises(RuntimeError, match="paper schema newer than application"):
                ensure_paper_schema(db)
            assert _schema(db) == schema_before
        else:
            assert ensure_paper_schema(db)["schema_version"] == 7
            after_first = _schema(db), _rows(db)
            assert ensure_paper_schema(db)["schema_version"] == 7
            assert (_schema(db), _rows(db)) == after_first
        assert db.execute("PRAGMA user_version").fetchone() == (version,)
        _assert_preserved(db, before)


def test_failed_schema7_upgrade_is_atomic(database):
    with sqlite3.connect(database) as db:
        before, schema_before = _rows(db), _schema(db)

        def deny_version_write(action, name, value, *_):
            if action == sqlite3.SQLITE_PRAGMA and name == "user_version" and value is not None:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(deny_version_write)
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            ensure_paper_schema(db)
        db.set_authorizer(None)
        assert db.execute("PRAGMA user_version").fetchone() == (6,)
        assert _schema(db) == schema_before
        assert _rows(db) == before
