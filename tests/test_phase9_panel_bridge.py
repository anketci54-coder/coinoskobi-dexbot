import json
import sqlite3

from app.dex.phase9_panel_bridge import (
    TRIGGER_NAME,
    apply_phase9_panel_bridge,
)


def _db(tmp_path, *, strict_success=False):
    path = tmp_path / "paper.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE candidate_decision_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observed_at REAL NOT NULL,
            context_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE wallet_discovery_registry (
            wallet_uid TEXT,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        );

        CREATE TABLE whale_activity_snapshot (
            wallet_uid TEXT,
            generated_at REAL,
            whale_state TEXT,
            direction TEXT,
            activity_score REAL,
            evidence_count INTEGER
        );
        """
    )

    if strict_success:
        con.execute(
            """
            CREATE TABLE wallet_success_score (
                wallet_uid TEXT,
                calculated_at REAL NOT NULL,
                sample_depth INTEGER NOT NULL,
                consistency_score REAL NOT NULL,
                entry_quality_score REAL,
                exit_quality_score REAL,
                loss_control_score REAL,
                risk_adjusted_score REAL,
                freshness_score REAL,
                success_score REAL,
                qualification_state TEXT NOT NULL
            )
            """
        )
    else:
        con.execute(
            """
            CREATE TABLE wallet_success_score (
                wallet_uid TEXT,
                calculated_at REAL,
                sample_depth INTEGER,
                consistency_score REAL,
                entry_quality_score REAL,
                exit_quality_score REAL,
                loss_control_score REAL,
                risk_adjusted_score REAL,
                freshness_score REAL,
                success_score REAL,
                qualification_state TEXT
            )
            """
        )

    con.commit()
    con.close()
    return path


def _context(wallet, *, performance="UNKNOWN", whale_ready=False, whale_state="UNKNOWN"):
    return {
        "runtime_intelligence": {
            "wallet_readmodel": {
                "payload": {
                    "wallet_id": wallet,
                    "identity_source": "TRANSACTION_FROM_ONLY",
                    "phase9_wallet_tracking": {
                        "performance": {
                            "state": performance,
                            "realized_sample_size": 24,
                        }
                    },
                    "whale_value_evidence_ready": whale_ready,
                    "whale_state": whale_state,
                }
            }
        }
    }


def _insert(path, context, observed_at=1000.0):
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO candidate_decision_history(observed_at, context_json) VALUES(?,?)",
        (observed_at, json.dumps(context)),
    )
    con.commit()
    con.close()


def test_bridge_backfills_real_actor_and_is_idempotent(tmp_path):
    path = _db(tmp_path)
    wallet = "bsc:0x0000000000000000000000000000000000000101"
    _insert(path, _context(wallet))

    first = apply_phase9_panel_bridge(path)
    second = apply_phase9_panel_bridge(path)

    assert first["tracked_wallets"] == 1
    assert second["tracked_wallets"] == 1
    assert first["successful_wallets"] == 0
    assert first["active_whales"] == 0
    assert first["trigger_installed"] is True
    assert first["panel_read_only"] is True
    assert first["execution_authority"] is False

    con = sqlite3.connect(path)
    row = con.execute(
        "SELECT wallet_uid, chain, address, discovery_source FROM wallet_discovery_registry"
    ).fetchone()
    trigger = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?",
        (TRIGGER_NAME,),
    ).fetchone()
    con.close()

    assert row == (
        wallet,
        "bsc",
        "0x0000000000000000000000000000000000000101",
        "TRANSACTION_FROM_ONLY",
    )
    assert trigger is not None


def test_trigger_tracks_future_real_actor_only(tmp_path):
    path = _db(tmp_path)
    apply_phase9_panel_bridge(path)

    wallet = "bsc:0x0000000000000000000000000000000000000202"
    _insert(path, _context(wallet), observed_at=2000.0)

    fake = _context("bsc:0x0000000000000000000000000000000000000303")
    fake["runtime_intelligence"]["wallet_readmodel"]["payload"]["identity_source"] = "ROUTER_GUESS"
    _insert(path, fake, observed_at=2001.0)

    con = sqlite3.connect(path)
    rows = con.execute(
        "SELECT wallet_uid FROM wallet_discovery_registry ORDER BY wallet_uid"
    ).fetchall()
    con.close()

    assert rows == [(wallet,)]


def test_success_and_whale_require_explicit_phase9_evidence(tmp_path):
    path = _db(tmp_path)
    apply_phase9_panel_bridge(path)

    successful = "bsc:0x0000000000000000000000000000000000000404"
    _insert(path, _context(successful, performance="SUCCESSFUL"), 3000.0)

    whale = "bsc:0x0000000000000000000000000000000000000505"
    _insert(
        path,
        _context(
            whale,
            performance="OBSERVED",
            whale_ready=True,
            whale_state="WHALE_CONFIRMED",
        ),
        3001.0,
    )

    con = sqlite3.connect(path)
    success_rows = con.execute(
        "SELECT wallet_uid, qualification_state, sample_depth FROM wallet_success_score"
    ).fetchall()
    whale_rows = con.execute(
        "SELECT wallet_uid, whale_state, direction FROM whale_activity_snapshot"
    ).fetchall()
    con.close()

    assert success_rows == [(successful, "SUCCESSFUL", 24)]
    assert whale_rows == [(whale, "WHALE_CONFIRMED", "UNKNOWN")]


def test_strict_legacy_constraints_cannot_break_decision_insert(tmp_path):
    path = _db(tmp_path, strict_success=True)
    apply_phase9_panel_bridge(path)

    wallet = "bsc:0x0000000000000000000000000000000000000606"
    _insert(path, _context(wallet, performance="SUCCESSFUL"), 4000.0)

    con = sqlite3.connect(path)
    decision_count = con.execute(
        "SELECT COUNT(*) FROM candidate_decision_history"
    ).fetchone()[0]
    wallet_count = con.execute(
        "SELECT COUNT(*) FROM wallet_discovery_registry"
    ).fetchone()[0]
    success_count = con.execute(
        "SELECT COUNT(*) FROM wallet_success_score"
    ).fetchone()[0]
    qualification = con.execute(
        "SELECT qualification_state FROM wallet_success_score"
    ).fetchone()[0]
    con.close()

    assert decision_count == 1
    assert wallet_count == 1
    assert success_count == 1
    assert qualification == "SUCCESSFUL"
