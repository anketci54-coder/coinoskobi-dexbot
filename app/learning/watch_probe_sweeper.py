from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from app.learning.watch_probe_exit import (
    MAX_PROBES_PER_MINUTE,
    RETRY_SECONDS,
    probe_watch_exit,
)
from app.paper.database import DB as PAPER_DB


TIME_EXIT_SECONDS = 3600.0


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _ensure_time_trigger(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    now: float,
) -> None:
    elapsed = float(now) - float(row["opened_at"])
    if elapsed < TIME_EXIT_SECONDS:
        return

    probe_id = int(row["id"])
    price = (
        _positive(row["last_price"])
        or _positive(row["entry_price"])
    )
    entry = _positive(row["entry_price"])
    return_pct = None
    if price is not None and entry is not None:
        return_pct = ((price / entry) - 1.0) * 100.0

    connection.execute(
        """
        INSERT INTO watch_probe_shadow_exits(
            probe_id,
            strategy,
            triggered_at,
            trigger_price,
            return_pct,
            state,
            reason
        )
        VALUES(?,?,?,?,?,'TRIGGERED','TIME_60M')
        ON CONFLICT(probe_id, strategy) DO UPDATE SET
            triggered_at=COALESCE(watch_probe_shadow_exits.triggered_at, excluded.triggered_at),
            trigger_price=COALESCE(watch_probe_shadow_exits.trigger_price, excluded.trigger_price),
            return_pct=COALESCE(watch_probe_shadow_exits.return_pct, excluded.return_pct),
            state=CASE
                WHEN watch_probe_shadow_exits.state='ARMED' THEN 'TRIGGERED'
                ELSE watch_probe_shadow_exits.state
            END,
            reason=CASE
                WHEN watch_probe_shadow_exits.state='ARMED' THEN 'TIME_60M'
                ELSE watch_probe_shadow_exits.reason
            END
        """,
        (
            probe_id,
            "TIME_60M",
            float(now),
            price,
            return_pct,
        ),
    )


def _persist_result(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    result: dict[str, Any],
    now: float,
) -> bool:
    if not result.get("attempted"):
        return False

    state = str(result.get("state") or "UNVERIFIED").upper()
    quality = result.get("quality")
    reason = result.get("reason")
    exit_usdt = _positive(result.get("realizable_exit_usdt"))
    entry_usdt = _positive(row["entry_usdt"])
    return_pct = None

    if exit_usdt is not None and entry_usdt is not None:
        return_pct = ((exit_usdt / entry_usdt) - 1.0) * 100.0

    verified = state == "VERIFIED" and exit_usdt is not None

    connection.execute(
        """
        UPDATE watch_probe_trades
        SET
            realizable_exit_usdt=?,
            realizable_return_pct=?,
            exit_state=?,
            exit_quality=?,
            exit_reason=?,
            last_exit_probe_at=?,
            status=CASE WHEN ? THEN 'CLOSED' ELSE status END,
            closed_at=CASE WHEN ? THEN ? ELSE closed_at END,
            context_version='WATCH_PROBE_EXIT_V1'
        WHERE id=?
          AND status='OPEN'
        """,
        (
            exit_usdt,
            return_pct,
            state,
            quality,
            reason,
            float(now),
            1 if verified else 0,
            1 if verified else 0,
            float(now),
            int(row["id"]),
        ),
    )

    return verified


def sweep_watch_probe_exits(
    db_path: Path | str,
    *,
    now: float | None = None,
    max_entries: int = MAX_PROBES_PER_MINUTE,
) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {
            "state": "NO_DB",
            "selected": 0,
            "attempted": 0,
            "verified": 0,
            "deferred": 0,
            "bounded": True,
        }

    now = time.time() if now is None else float(now)
    limit = max(1, min(int(max_entries), MAX_PROBES_PER_MINUTE))

    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000;")

    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='watch_probe_trades'"
        ).fetchone()
        if not exists:
            return {
                "state": "NO_TABLE",
                "selected": 0,
                "attempted": 0,
                "verified": 0,
                "deferred": 0,
                "bounded": True,
            }

        rows = connection.execute(
            """
            SELECT
                id,
                token,
                pool,
                opened_at,
                entry_price,
                entry_usdt,
                token_amount,
                last_price,
                exit_state,
                last_exit_probe_at
            FROM watch_probe_trades
            WHERE status='OPEN'
              AND UPPER(COALESCE(exit_state,'UNVERIFIED')) != 'VERIFIED'
              AND (
                    last_exit_probe_at IS NULL
                    OR last_exit_probe_at <= ?
              )
              AND (
                    opened_at <= ?
                    OR EXISTS(
                        SELECT 1
                        FROM watch_probe_shadow_exits x
                        WHERE x.probe_id=watch_probe_trades.id
                          AND x.state='TRIGGERED'
                    )
              )
            ORDER BY
                CASE WHEN last_exit_probe_at IS NULL THEN 0 ELSE 1 END,
                COALESCE(last_exit_probe_at, opened_at),
                id
            LIMIT ?
            """,
            (
                float(now) - RETRY_SECONDS,
                float(now) - TIME_EXIT_SECONDS,
                limit,
            ),
        ).fetchall()

        attempted = 0
        verified = 0
        deferred = 0

        for row in rows:
            _ensure_time_trigger(connection, row, now)
            connection.commit()

            result = probe_watch_exit(
                token=row["token"],
                pool=row["pool"],
                token_amount=row["token_amount"],
                now=now,
            )

            if result.get("attempted"):
                attempted += 1
            else:
                deferred += 1

            if _persist_result(connection, row, result, now):
                verified += 1

            connection.commit()

        return {
            "state": "READY",
            "selected": len(rows),
            "attempted": attempted,
            "verified": verified,
            "deferred": deferred,
            "bounded": True,
            "max_entries": limit,
            "trade_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
    finally:
        connection.close()


def sweep_default_watch_probe_exits() -> dict[str, Any]:
    return sweep_watch_probe_exits(PAPER_DB)
