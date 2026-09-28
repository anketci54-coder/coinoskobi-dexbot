"""Create an auditable PAPER run boundary without altering economic history."""
import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

from app.paper.calibration_provenance import CURRENT_PAPER_MODEL, current_model_open_position
from app.paper.schema import PAPER_POSITION_QUARANTINES_SCHEMA, PAPER_RUNS_SCHEMA
from app.risk.paper_position_sizing import PAPER_CAPITAL_USDT, _active_paper_run


def start_paper_run(db_path, run_key, *, apply=False, quarantine_unproven_open=False):
    run_key = str(run_key).strip()
    if not run_key:
        raise ValueError("PAPER_RUN_KEY_REQUIRED")
    path = Path(db_path).resolve()
    # mode=rw prevents accidentally creating a fresh DB at a mistyped path.
    with closing(sqlite3.connect(path.as_uri() + ("?mode=rw" if apply else "?mode=ro"),
                                 uri=True, timeout=30)) as db:
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
            active = _active_paper_run(db)
            runs_exist = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='paper_runs'"
            ).fetchone()
            previous = (db.execute("SELECT * FROM paper_runs WHERE run_key=?", (run_key,)).fetchone()
                        if runs_exist else None)
            if previous:
                if active and previous["id"] == active["id"]:
                    db.rollback()
                    return {"state": "ALREADY_ACTIVE", "run": dict(previous)}
                raise ValueError("PAPER_RUN_KEY_ALREADY_USED")
            open_rows = db.execute(
                """
                SELECT
                    id AS position_id,
                    created_at,
                    token,
                    pool,
                    entry_price,
                    opening_context_json,
                    paper_run_id,
                    status
                FROM paper_trades
                WHERE UPPER(TRIM(COALESCE(status,'')))='OPEN'
                ORDER BY id
                """
            ).fetchall()
            proven_open = [row for row in open_rows if current_model_open_position(row)]
            unproven_open = [row for row in open_rows if not current_model_open_position(row)]

            if open_rows and not quarantine_unproven_open:
                raise ValueError("PAPER_RUN_BOUNDARY_HAS_OPEN_POSITIONS")
            if proven_open:
                raise ValueError("PAPER_RUN_BOUNDARY_HAS_CURRENT_MODEL_OPEN_POSITIONS")

            quarantine = {
                "requested": bool(quarantine_unproven_open),
                "count": len(unproven_open),
                "position_ids": [int(row["position_id"]) for row in unproven_open],
                "reason": "UNPROVEN_LEGACY_OPEN_AT_CORRECTED_RUN_BOUNDARY",
            }

            if apply and unproven_open:
                db.execute(PAPER_POSITION_QUARANTINES_SCHEMA)
                quarantined_at = datetime.now(timezone.utc).isoformat()
                for row in unproven_open:
                    metadata = json.dumps({
                        "model": CURRENT_PAPER_MODEL,
                        "history_preserved": True,
                        "economic_fields_rewritten": False,
                        "previous_active_run_id": active["id"] if active else None,
                    }, sort_keys=True)
                    db.execute(
                        """
                        INSERT INTO paper_position_quarantines(
                            position_id,
                            quarantined_at,
                            previous_status,
                            reason,
                            previous_run_id,
                            metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(row["position_id"]),
                            quarantined_at,
                            str(row["status"]),
                            quarantine["reason"],
                            row["paper_run_id"],
                            metadata,
                        ),
                    )
                    changed = db.execute(
                        """
                        UPDATE paper_trades
                        SET status='QUARANTINED'
                        WHERE id=?
                          AND UPPER(TRIM(COALESCE(status,'')))='OPEN'
                        """,
                        (int(row["position_id"]),),
                    )
                    if changed.rowcount != 1:
                        raise RuntimeError("PAPER_RUN_QUARANTINE_RACE")

            if apply and db.execute(
                "SELECT 1 FROM paper_trades WHERE UPPER(TRIM(COALESCE(status,'')))='OPEN' LIMIT 1"
            ).fetchone():
                raise ValueError("PAPER_RUN_BOUNDARY_HAS_OPEN_POSITIONS")

            def boundary(table, required=True):
                exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists and not required:
                    return 0
                return int(db.execute(f"SELECT COALESCE(MAX(id),0) FROM {table}").fetchone()[0])

            run = {
                "run_key": run_key,
                "started_at": time.time(),
                "starting_capital_usdt": PAPER_CAPITAL_USDT,
                "start_trade_id": boundary("paper_trades"),
                "start_realization_id": boundary("paper_realizations"),
                "start_candidate_id": boundary("candidate_decision_history", required=False),
                "status": "ACTIVE",
                "metadata_json": json.dumps({
                    "model": CURRENT_PAPER_MODEL,
                    "previous_run_id": active["id"] if active else None,
                    "history_preserved": True,
                    "quarantined_unproven_open_count": quarantine["count"],
                }, sort_keys=True),
            }
            if apply:
                db.execute(PAPER_RUNS_SCHEMA)
                db.execute("UPDATE paper_runs SET status='COMPLETED' WHERE status='ACTIVE'")
                cursor = db.execute(
                    f"INSERT INTO paper_runs ({','.join(run)}) VALUES ({','.join('?' for _ in run)})",
                    tuple(run.values()),
                )
                run["id"] = cursor.lastrowid
                db.commit()
            else:
                db.rollback()
            return {
                "state": "CREATED" if apply else "PREVIEW",
                "run": run,
                "quarantine": quarantine,
            }
        except Exception:
            db.rollback()
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Existing PAPER database path")
    parser.add_argument("--run-key", required=True, help="Unique human-readable run name")
    parser.add_argument("--apply", action="store_true", help="Commit boundary; default is read-only preview")
    parser.add_argument(
        "--quarantine-unproven-open",
        action="store_true",
        help="Audit-quarantine only OPEN rows that cannot prove corrected-model admission",
    )
    args = parser.parse_args(argv)
    try:
        result = start_paper_run(
            args.db,
            args.run_key,
            apply=args.apply,
            quarantine_unproven_open=args.quarantine_unproven_open,
        )
    except (ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.exit(2, f"PAPER run boundary refused: {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
