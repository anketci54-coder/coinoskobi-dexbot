from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SNAPSHOT_KEY = "WATCH_OUTCOMES"


def watch_learning_snapshot(paper_db: Path | str) -> dict[str, Any]:
    """Read-only learning evidence derived only from durable WATCH outcomes."""
    path = Path(paper_db)
    if not path.exists():
        return {"available": False, "reason": "PAPER_DB_MISSING"}

    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        table = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='watch_probe_trades'"
        ).fetchone()
        if not table:
            return {"available": False, "reason": "WATCH_TABLE_MISSING"}

        row = con.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) AS closed_count,
                SUM(CASE WHEN UPPER(COALESCE(exit_state,''))='VERIFIED' THEN 1 ELSE 0 END) AS verified_count,
                SUM(CASE WHEN UPPER(COALESCE(exit_state,''))='LIMITED' THEN 1 ELSE 0 END) AS limited_count,
                SUM(CASE WHEN UPPER(COALESCE(exit_state,''))='UNVERIFIED' THEN 1 ELSE 0 END) AS unverified_count,
                SUM(CASE WHEN last_exit_probe_at IS NOT NULL THEN 1 ELSE 0 END) AS attempted_count,
                AVG(CASE
                    WHEN status='CLOSED'
                     AND entry_usdt > 0
                     AND realizable_exit_usdt IS NOT NULL
                    THEN ((realizable_exit_usdt / entry_usdt) - 1.0) * 100.0
                    ELSE NULL
                END) AS verified_avg_return_pct,
                SUM(CASE
                    WHEN status='CLOSED'
                     AND entry_usdt > 0
                     AND realizable_exit_usdt > entry_usdt
                    THEN 1 ELSE 0
                END) AS verified_wins
            FROM watch_probe_trades
            WHERE token <> '0xtoken'
            """
        ).fetchone()
    finally:
        con.close()

    total = int(row["total"] or 0)
    closed = int(row["closed_count"] or 0)
    verified = int(row["verified_count"] or 0)
    wins = int(row["verified_wins"] or 0)
    win_rate = (wins / verified) if verified else None

    confidence = "INSUFFICIENT"
    if verified >= 100:
        confidence = "HIGH"
    elif verified >= 30:
        confidence = "MEDIUM"
    elif verified >= 10:
        confidence = "LOW"

    return {
        "available": True,
        "total": total,
        "open": int(row["open_count"] or 0),
        "closed": closed,
        "verified": verified,
        "limited": int(row["limited_count"] or 0),
        "unverified": int(row["unverified_count"] or 0),
        "exit_attempted": int(row["attempted_count"] or 0),
        "verified_wins": wins,
        "verified_win_rate": win_rate,
        "verified_avg_return_pct": (
            float(row["verified_avg_return_pct"])
            if row["verified_avg_return_pct"] is not None
            else None
        ),
        "learning_confidence": confidence,
        "truth_rule": "Only VERIFIED durable exits calibrate performance.",
        "paper_db_write_authority": False,
        "trade_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
