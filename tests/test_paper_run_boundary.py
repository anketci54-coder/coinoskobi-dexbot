import json
import sqlite3
import subprocess
import sys
import threading

import pytest

from app.paper.database import PaperDatabase
from app.paper.run_boundary import start_paper_run
from app.paper.schema import ensure_paper_schema
from app.risk.paper_position_sizing import paper_available_capital_usdt
from tests.paper_calibration_fixtures import TOKEN, POOL, opening


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "paper.db"
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    ensure_paper_schema(db)
    db.execute("""INSERT INTO paper_trades (token, status, paper_account_version, net_pnl_usdt)
                  VALUES ('history', 'CLOSED', 'PAPER_10K_V2', -1200)""")
    db.execute("CREATE TABLE candidate_decision_history (id INTEGER PRIMARY KEY)")
    db.execute("INSERT INTO candidate_decision_history VALUES (9)")
    db.commit()
    yield path, db
    db.close()


def test_preview_and_apply_preserve_all_economic_rows(database):
    path, db = database
    before = db.execute("SELECT * FROM paper_trades").fetchall()
    assert paper_available_capital_usdt(db) == 8800
    assert start_paper_run(path, "clean")["state"] == "PREVIEW"
    assert db.execute("SELECT count(*) FROM paper_runs").fetchone()[0] == 0
    result = start_paper_run(path, "clean", apply=True)
    assert result["state"] == "CREATED"
    assert result["run"]["start_trade_id"] == 1
    assert result["run"]["start_candidate_id"] == 9
    assert paper_available_capital_usdt(db) == 10000
    assert db.execute("SELECT * FROM paper_trades").fetchall() == before
    assert start_paper_run(path, "clean", apply=True)["state"] == "ALREADY_ACTIVE"
    assert db.execute("SELECT count(*) FROM paper_runs").fetchone()[0] == 1
    start_paper_run(path, "next", apply=True)
    assert [row[0] for row in db.execute("SELECT status FROM paper_runs ORDER BY id")] == ["COMPLETED", "ACTIVE"]
    with pytest.raises(ValueError, match="KEY_ALREADY_USED"):
        start_paper_run(path, "clean", apply=True)
    assert db.execute("SELECT * FROM paper_trades").fetchall() == before


@pytest.mark.parametrize("status", ["OPEN", "open", " Open "])
def test_refuses_boundary_with_any_open_position(database, status):
    path, db = database
    db.execute("UPDATE paper_trades SET status=?", (status,))
    db.commit()
    before = db.execute("SELECT * FROM paper_trades").fetchall()
    for apply in (False, True):
        with pytest.raises(ValueError, match="HAS_OPEN_POSITIONS"):
            start_paper_run(path, "new", apply=apply)
    assert db.execute("SELECT * FROM paper_trades").fetchall() == before
    assert db.execute("SELECT count(*) FROM paper_runs").fetchone()[0] == 0


def test_insertion_binds_active_run_and_prevents_rotation(database):
    path, db = database
    run = start_paper_run(path, "clean", apply=True)["run"]
    store = object.__new__(PaperDatabase)
    store.conn, store._db_lock = db, threading.RLock()
    store.insert({"token": "new", "status": "OPEN", "paper_run_id": 999,
                  "paper_account_version": "PAPER_10K_V2", "entry_amount_usdt": 100})
    row = db.execute("SELECT * FROM paper_trades WHERE token='new'").fetchone()
    assert row["paper_run_id"] == run["id"]
    assert paper_available_capital_usdt(db) == 9900
    with pytest.raises(ValueError, match="HAS_OPEN_POSITIONS"):
        start_paper_run(path, "next", apply=True)


def test_cli_defaults_to_read_only_preview_and_refuses_missing_db(database, tmp_path):
    path, db = database
    command = [sys.executable, "-m", "app.paper.run_boundary", "--db", str(path), "--run-key", "cli"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "PREVIEW"
    assert db.execute("SELECT count(*) FROM paper_runs").fetchone()[0] == 0
    result = subprocess.run(command + ["--apply"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "CREATED"
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        start_paper_run(missing, "oops", apply=True)
    assert not missing.exists()


def test_boundary_cannot_pass_a_concurrent_entry(database):
    path, _ = database
    entry_locked, release_entry, boundary_finished = (threading.Event() for _ in range(3))
    results = []

    def insert():
        store = object.__new__(PaperDatabase)
        store.conn = sqlite3.connect(path)
        store._db_lock = threading.RLock()
        original = store._insert_unlocked

        def paused(trade):
            entry_locked.set()
            assert release_entry.wait(2)
            original(trade)

        store._insert_unlocked = paused
        try:
            store.insert({"token": "concurrent", "status": "OPEN"})
        finally:
            store.conn.close()

    def rotate():
        try:
            results.append(start_paper_run(path, "racing", apply=True))
        except ValueError as exc:
            results.append(str(exc))
        finally:
            boundary_finished.set()

    entry = threading.Thread(target=insert)
    boundary = threading.Thread(target=rotate)
    entry.start()
    assert entry_locked.wait(1)
    boundary.start()
    try:
        assert not boundary_finished.wait(.05)
    finally:
        release_entry.set()
        entry.join(3)
        boundary.join(3)
    assert not entry.is_alive() and not boundary.is_alive()
    assert results == ["PAPER_RUN_BOUNDARY_HAS_OPEN_POSITIONS"]

def test_explicit_quarantine_preserves_legacy_open_economics_and_starts_clean_run(database):
    path, db = database
    db.execute(
        """INSERT INTO paper_trades (
            token, pool, status, paper_account_version, entry_price,
            entry_amount_usdt, token_amount, remaining_cost_basis_usdt,
            realized_pnl_usdt, opening_context_json
        ) VALUES ('legacy', 'legacy-pool', 'OPEN', 'PAPER_10K_V2', 2,
                  321, 123, 111, 7, '{}')"""
    )
    db.commit()
    position_id = db.execute(
        "SELECT id FROM paper_trades WHERE token='legacy'"
    ).fetchone()[0]
    economics_before = db.execute(
        """SELECT entry_price, entry_amount_usdt, token_amount,
                  remaining_cost_basis_usdt, realized_pnl_usdt
           FROM paper_trades WHERE id=?""",
        (position_id,),
    ).fetchone()

    preview = start_paper_run(
        path, "clean-quarantine", quarantine_unproven_open=True
    )
    assert preview["state"] == "PREVIEW"
    assert preview["quarantine"]["position_ids"] == [position_id]
    assert db.execute(
        "SELECT status FROM paper_trades WHERE id=?", (position_id,)
    ).fetchone()[0] == "OPEN"
    assert db.execute(
        "SELECT count(*) FROM paper_position_quarantines"
    ).fetchone()[0] == 0

    result = start_paper_run(
        path, "clean-quarantine", apply=True, quarantine_unproven_open=True
    )
    assert result["state"] == "CREATED"
    assert result["quarantine"]["position_ids"] == [position_id]
    assert result["run"]["start_trade_id"] == position_id
    assert db.execute(
        "SELECT status FROM paper_trades WHERE id=?", (position_id,)
    ).fetchone()[0] == "QUARANTINED"
    assert db.execute(
        """SELECT entry_price, entry_amount_usdt, token_amount,
                  remaining_cost_basis_usdt, realized_pnl_usdt
           FROM paper_trades WHERE id=?""",
        (position_id,),
    ).fetchone() == economics_before
    audit = db.execute(
        """SELECT previous_status, reason, previous_run_id, metadata_json
           FROM paper_position_quarantines WHERE position_id=?""",
        (position_id,),
    ).fetchone()
    assert audit["previous_status"] == "OPEN"
    assert audit["reason"] == "UNPROVEN_LEGACY_OPEN_AT_CORRECTED_RUN_BOUNDARY"
    assert json.loads(audit["metadata_json"])["economic_fields_rewritten"] is False
    assert db.execute(
        "SELECT count(*) FROM paper_trades WHERE status='OPEN'"
    ).fetchone()[0] == 0
    assert paper_available_capital_usdt(db) == 10000


def test_quarantine_refuses_any_current_model_open_position(database):
    path, db = database
    db.execute(
        """INSERT INTO paper_trades (
            token, pool, status, paper_account_version, entry_price,
            entry_amount_usdt, opening_context_json
        ) VALUES (?, ?, 'OPEN', 'PAPER_10K_V2', 1, 100, ?)""",
        (TOKEN, POOL, json.dumps(opening(1.0))),
    )
    db.execute(
        """INSERT INTO paper_trades (
            token, pool, status, paper_account_version, entry_price,
            entry_amount_usdt, opening_context_json
        ) VALUES ('legacy', 'legacy-pool', 'OPEN', 'PAPER_10K_V2', 1, 50, '{}')"""
    )
    db.commit()
    before = db.execute(
        "SELECT id, status, entry_amount_usdt FROM paper_trades ORDER BY id"
    ).fetchall()

    for apply in (False, True):
        with pytest.raises(
            ValueError, match="HAS_CURRENT_MODEL_OPEN_POSITIONS"
        ):
            start_paper_run(
                path,
                "must-refuse",
                apply=apply,
                quarantine_unproven_open=True,
            )

    assert db.execute(
        "SELECT id, status, entry_amount_usdt FROM paper_trades ORDER BY id"
    ).fetchall() == before
    assert db.execute(
        "SELECT count(*) FROM paper_position_quarantines"
    ).fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM paper_runs").fetchone()[0] == 0
