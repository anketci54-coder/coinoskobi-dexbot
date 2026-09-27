"""Create an auditable PAPER run boundary without altering economic history."""
import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from app.paper.calibration_provenance import CURRENT_PAPER_MODEL
from app.paper.schema import PAPER_RUNS_SCHEMA
from app.risk.paper_position_sizing import PAPER_CAPITAL_USDT, _active_paper_run


def start_paper_run(db_path, run_key, *, apply=False):
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
            if db.execute(
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
            return {"state": "CREATED" if apply else "PREVIEW", "run": run}
        except Exception:
            db.rollback()
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Existing PAPER database path")
    parser.add_argument("--run-key", required=True, help="Unique human-readable run name")
    parser.add_argument("--apply", action="store_true", help="Commit boundary; default is read-only preview")
    args = parser.parse_args(argv)
    try:
        result = start_paper_run(args.db, args.run_key, apply=args.apply)
    except (ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.exit(2, f"PAPER run boundary refused: {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
