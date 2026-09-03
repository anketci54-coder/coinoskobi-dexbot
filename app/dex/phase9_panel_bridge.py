from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_BACKFILL_LIMIT = 5000
TRIGGER_NAME = "phase9_panel_readmodel_after_decision"

_PATHS = (
    ("runtime_intelligence", "wallet_readmodel", "payload"),
    ("mathematical_plan", "market_context", "runtime_intelligence", "wallet_readmodel", "payload"),
)


def _get(value: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _payload(context: Any) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None
    for path in _PATHS:
        row = _get(context, path)
        if not isinstance(row, dict):
            continue
        wallet = str(row.get("wallet_id") or "").strip().lower()
        source = str(row.get("identity_source") or "").strip().upper()
        if wallet and source == "TRANSACTION_FROM_ONLY":
            return row
    return None


def _wallet_parts(value: Any) -> tuple[str, str, str] | None:
    wallet = str(value or "").strip().lower()
    if ":" not in wallet:
        return None
    chain, address = wallet.split(":", 1)
    if not chain or not address:
        return None
    return wallet, chain, address


def _ensure_tables(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS wallet_discovery_registry(
      wallet_uid TEXT PRIMARY KEY, chain TEXT, address TEXT,
      first_seen_at REAL, last_seen_at REAL, discovery_source TEXT,
      freshness_state TEXT, lifecycle_state TEXT
    );
    CREATE TABLE IF NOT EXISTS wallet_success_score(
      wallet_uid TEXT PRIMARY KEY, calculated_at REAL, sample_depth INTEGER,
      consistency_score REAL, entry_quality_score REAL, exit_quality_score REAL,
      loss_control_score REAL, risk_adjusted_score REAL, freshness_score REAL,
      success_score REAL, qualification_state TEXT
    );
    CREATE TABLE IF NOT EXISTS whale_activity_snapshot(
      wallet_uid TEXT PRIMARY KEY, generated_at REAL, whale_state TEXT,
      direction TEXT, activity_score REAL, evidence_count INTEGER
    );
    """)


def _write(db: sqlite3.Connection, payload: dict[str, Any], observed_at: Any) -> bool:
    parts = _wallet_parts(payload.get("wallet_id"))
    try:
        seen = float(observed_at)
    except (TypeError, ValueError):
        return False
    if parts is None:
        return False
    wallet, chain, address = parts

    db.execute("""
      INSERT OR IGNORE INTO wallet_discovery_registry(
        wallet_uid,chain,address,first_seen_at,last_seen_at,
        discovery_source,freshness_state,lifecycle_state
      ) SELECT ?,?,?,?,?,'TRANSACTION_FROM_ONLY','FRESH','ACTIVE'
        WHERE NOT EXISTS (SELECT 1 FROM wallet_discovery_registry WHERE lower(wallet_uid)=lower(?))
    """, (wallet, chain, address, seen, seen, wallet))
    db.execute("""
      UPDATE wallet_discovery_registry
      SET last_seen_at=?, discovery_source='TRANSACTION_FROM_ONLY',
          freshness_state='FRESH', lifecycle_state='ACTIVE'
      WHERE lower(wallet_uid)=lower(?)
    """, (seen, wallet))

    tracking = payload.get("phase9_wallet_tracking")
    tracking = tracking if isinstance(tracking, dict) else {}
    perf = tracking.get("performance")
    perf = perf if isinstance(perf, dict) else {}
    if str(perf.get("state") or "").upper() == "SUCCESSFUL":
        sample = perf.get("realized_sample_size")
        db.execute("""
          UPDATE wallet_success_score
          SET calculated_at=?, sample_depth=COALESCE(?,sample_depth),
              qualification_state='SUCCESSFUL'
          WHERE lower(wallet_uid)=lower(?)
        """, (seen, sample, wallet))
        try:
            db.execute("""
              INSERT OR IGNORE INTO wallet_success_score(
                wallet_uid,calculated_at,sample_depth,consistency_score,
                entry_quality_score,exit_quality_score,loss_control_score,
                risk_adjusted_score,freshness_score,success_score,qualification_state
              ) SELECT ?,?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'SUCCESSFUL'
                WHERE NOT EXISTS (SELECT 1 FROM wallet_success_score WHERE lower(wallet_uid)=lower(?))
            """, (wallet, seen, sample, wallet))
        except sqlite3.IntegrityError:
            pass

    whale_ready = payload.get("whale_value_evidence_ready") is True
    whale_state = str(payload.get("whale_state") or "").strip().upper()
    if whale_ready and whale_state not in {"", "UNKNOWN", "NONE"}:
        direction = str(payload.get("whale_direction") or "UNKNOWN").strip().upper() or "UNKNOWN"
        db.execute("""
          UPDATE whale_activity_snapshot
          SET generated_at=?, whale_state=?, direction=?
          WHERE lower(wallet_uid)=lower(?)
        """, (seen, whale_state, direction, wallet))
        try:
            db.execute("""
              INSERT OR IGNORE INTO whale_activity_snapshot(
                wallet_uid,generated_at,whale_state,direction,activity_score,evidence_count
              ) SELECT ?,?,?,?,NULL,NULL
                WHERE NOT EXISTS (SELECT 1 FROM whale_activity_snapshot WHERE lower(wallet_uid)=lower(?))
            """, (wallet, seen, whale_state, direction, wallet))
        except sqlite3.IntegrityError:
            pass
    return True


def _backfill(db: sqlite3.Connection, limit: int) -> tuple[int, int]:
    rows = db.execute("""
      SELECT observed_at,context_json FROM candidate_decision_history
      ORDER BY id DESC LIMIT ?
    """, (max(1, int(limit)),)).fetchall()
    accepted = 0
    for row in reversed(rows):
        try:
            context = json.loads(row["context_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        payload = _payload(context)
        if payload is not None and _write(db, payload, row["observed_at"]):
            accepted += 1
    return len(rows), accepted


def _json(primary: str, fallback: str, suffix: str) -> str:
    return (
        "COALESCE("
        f"CASE WHEN json_valid(NEW.context_json) THEN json_extract(NEW.context_json,'{primary}.{suffix}') END,"
        f"CASE WHEN json_valid(NEW.context_json) THEN json_extract(NEW.context_json,'{fallback}.{suffix}') END"
        ")"
    )


def _install_trigger(db: sqlite3.Connection) -> None:
    primary = "$.runtime_intelligence.wallet_readmodel.payload"
    fallback = "$.mathematical_plan.market_context.runtime_intelligence.wallet_readmodel.payload"
    wallet = f"lower({_json(primary, fallback, 'wallet_id')})"
    source = f"upper({_json(primary, fallback, 'identity_source')})"
    perf = f"upper({_json(primary, fallback, 'phase9_wallet_tracking.performance.state')})"
    sample = _json(primary, fallback, "phase9_wallet_tracking.performance.realized_sample_size")
    whale_ready = _json(primary, fallback, "whale_value_evidence_ready")
    whale_state = f"upper({_json(primary, fallback, 'whale_state')})"
    direction = f"upper(COALESCE({_json(primary, fallback, 'whale_direction')},'UNKNOWN'))"

    db.executescript(f"""
    DROP TRIGGER IF EXISTS {TRIGGER_NAME};
    CREATE TRIGGER {TRIGGER_NAME}
    AFTER INSERT ON candidate_decision_history
    WHEN COALESCE({source},'')='TRANSACTION_FROM_ONLY'
     AND COALESCE({wallet},'')<>''
    BEGIN
      INSERT OR IGNORE INTO wallet_discovery_registry(
        wallet_uid,chain,address,first_seen_at,last_seen_at,
        discovery_source,freshness_state,lifecycle_state
      ) SELECT {wallet},
        substr({wallet},1,instr({wallet},':')-1),
        substr({wallet},instr({wallet},':')+1),
        NEW.observed_at,NEW.observed_at,'TRANSACTION_FROM_ONLY','FRESH','ACTIVE'
        WHERE NOT EXISTS (SELECT 1 FROM wallet_discovery_registry WHERE lower(wallet_uid)={wallet});
      UPDATE wallet_discovery_registry
        SET last_seen_at=NEW.observed_at,discovery_source='TRANSACTION_FROM_ONLY',
            freshness_state='FRESH',lifecycle_state='ACTIVE'
        WHERE lower(wallet_uid)={wallet};

      UPDATE wallet_success_score
        SET calculated_at=NEW.observed_at,sample_depth=COALESCE({sample},sample_depth),
            qualification_state='SUCCESSFUL'
        WHERE lower(wallet_uid)={wallet} AND COALESCE({perf},'')='SUCCESSFUL';
      INSERT OR IGNORE INTO wallet_success_score(
        wallet_uid,calculated_at,sample_depth,consistency_score,entry_quality_score,
        exit_quality_score,loss_control_score,risk_adjusted_score,freshness_score,
        success_score,qualification_state
      ) SELECT {wallet},NEW.observed_at,{sample},NULL,NULL,NULL,NULL,NULL,NULL,NULL,'SUCCESSFUL'
        WHERE COALESCE({perf},'')='SUCCESSFUL'
          AND NOT EXISTS (SELECT 1 FROM wallet_success_score WHERE lower(wallet_uid)={wallet});

      UPDATE whale_activity_snapshot
        SET generated_at=NEW.observed_at,whale_state={whale_state},direction={direction}
        WHERE lower(wallet_uid)={wallet} AND COALESCE({whale_ready},0)=1
          AND COALESCE({whale_state},'') NOT IN ('','UNKNOWN','NONE');
      INSERT OR IGNORE INTO whale_activity_snapshot(
        wallet_uid,generated_at,whale_state,direction,activity_score,evidence_count
      ) SELECT {wallet},NEW.observed_at,{whale_state},{direction},NULL,NULL
        WHERE COALESCE({whale_ready},0)=1
          AND COALESCE({whale_state},'') NOT IN ('','UNKNOWN','NONE')
          AND NOT EXISTS (SELECT 1 FROM whale_activity_snapshot WHERE lower(wallet_uid)={wallet});
    END;
    """)


def apply_phase9_panel_bridge(db_path: str | Path, *, backfill_limit: int = DEFAULT_BACKFILL_LIMIT) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(path)
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    try:
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='candidate_decision_history'").fetchone() is None:
            raise RuntimeError("candidate_decision_history missing")
        _ensure_tables(db)
        scanned, accepted = _backfill(db, backfill_limit)
        _install_trigger(db)
        db.commit()
        count = lambda table: int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        return {
            "state": "READY",
            "backfill_scanned": scanned,
            "backfill_phase9_rows": accepted,
            "tracked_wallets": count("wallet_discovery_registry"),
            "successful_wallets": count("wallet_success_score"),
            "active_whales": count("whale_activity_snapshot"),
            "trigger_installed": db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?", (TRIGGER_NAME,)
            ).fetchone() is not None,
            "panel_read_only": True,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/paper_trades.db")
    parser.add_argument("--backfill-limit", type=int, default=DEFAULT_BACKFILL_LIMIT)
    args = parser.parse_args()
    result = apply_phase9_panel_bridge(args.db, backfill_limit=args.backfill_limit)
    print("PHASE9_PANEL_BRIDGE_STATE=" + result["state"])
    print("BACKFILL_SCANNED=" + str(result["backfill_scanned"]))
    print("BACKFILL_PHASE9_ROWS=" + str(result["backfill_phase9_rows"]))
    print("TRACKED_WALLETS=" + str(result["tracked_wallets"]))
    print("SUCCESSFUL_WALLETS=" + str(result["successful_wallets"]))
    print("ACTIVE_WHALES=" + str(result["active_whales"]))
    print("TRIGGER_INSTALLED=" + str(result["trigger_installed"]).lower())
    print("PANEL_READ_ONLY=true")
    print("PHASE9_PANEL_BRIDGE=PASS")


if __name__ == "__main__":
    main()
