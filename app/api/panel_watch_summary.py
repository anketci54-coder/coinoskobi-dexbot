from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def watch_probe_summary(paper_db: Path) -> dict[str, Any]:
    if not paper_db.exists():
        return {
            "available": False,
            "count": 0,
            "open": 0,
            "closed": 0,
            "entry_usdt_total": 0.0,
            "mark_value_usdt": 0.0,
            "mark_pnl_usdt": 0.0,
            "verified": 0,
            "limited": 0,
            "verified_exit_usdt": 0.0,
        }

    connection = sqlite3.connect(
        f"file:{paper_db}?mode=ro",
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row

    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='watch_probe_trades'"
        ).fetchone()
        if not exists:
            return {
                "available": False,
                "count": 0,
                "open": 0,
                "closed": 0,
                "entry_usdt_total": 0.0,
                "mark_value_usdt": 0.0,
                "mark_pnl_usdt": 0.0,
                "verified": 0,
                "limited": 0,
                "verified_exit_usdt": 0.0,
            }

        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(watch_probe_trades)").fetchall()
        }
        has_exit_state = "exit_state" in columns
        has_realizable = "realizable_exit_usdt" in columns

        exit_state_sql = (
            "SUM(CASE WHEN UPPER(COALESCE(exit_state,''))='VERIFIED' THEN 1 ELSE 0 END)"
            if has_exit_state else "0"
        )
        limited_sql = (
            "SUM(CASE WHEN UPPER(COALESCE(exit_state,''))='LIMITED' THEN 1 ELSE 0 END)"
            if has_exit_state else "0"
        )
        verified_exit_sql = (
            "SUM(CASE WHEN UPPER(COALESCE(exit_state,''))='VERIFIED' "
            "THEN COALESCE(realizable_exit_usdt,0) ELSE 0 END)"
            if has_exit_state and has_realizable else "0"
        )

        row = connection.execute(
            f"""
            SELECT
                COUNT(*) AS count,
                SUM(CASE WHEN UPPER(COALESCE(status,''))='OPEN' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN UPPER(COALESCE(status,''))='CLOSED' THEN 1 ELSE 0 END) AS closed_count,
                COALESCE(SUM(COALESCE(entry_usdt,0)),0) AS entry_total,
                COALESCE(SUM(
                    CASE
                    WHEN COALESCE(token_amount,0) > 0 AND COALESCE(last_price,0) > 0
                    THEN token_amount * last_price
                    ELSE COALESCE(entry_usdt,0)
                    END
                ),0) AS mark_total,
                COALESCE({exit_state_sql},0) AS verified_count,
                COALESCE({limited_sql},0) AS limited_count,
                COALESCE({verified_exit_sql},0) AS verified_exit_total
            FROM watch_probe_trades
            WHERE token != '0xtoken'
            """
        ).fetchone()

        entry_total = float(row["entry_total"] or 0.0)
        mark_total = float(row["mark_total"] or 0.0)

        return {
            "available": True,
            "count": int(row["count"] or 0),
            "open": int(row["open_count"] or 0),
            "closed": int(row["closed_count"] or 0),
            "entry_usdt_total": entry_total,
            "mark_value_usdt": mark_total,
            "mark_pnl_usdt": mark_total - entry_total,
            "verified": int(row["verified_count"] or 0),
            "limited": int(row["limited_count"] or 0),
            "verified_exit_usdt": float(row["verified_exit_total"] or 0.0),
        }
    finally:
        connection.close()


def register_watch_summary_route(app, *, paper_db: Path) -> None:
    @app.get("/api/watch-probes-summary-v2")
    def api_watch_probe_summary_v2() -> dict[str, Any]:
        return watch_probe_summary(paper_db)
