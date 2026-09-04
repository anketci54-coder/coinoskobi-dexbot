from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


MAX_RECENT_TURNS = 8
MAX_MEMORY_TEXT = 800


class VezirMemoryStore:
    """Separate, bounded Vezir memory. Never writes to the paper DB."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _ensure_schema(self) -> None:
        con = self._connect()
        try:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS vezir_turns(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    intent TEXT,
                    ai_used INTEGER NOT NULL DEFAULT 0,
                    provider TEXT,
                    truth_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_vezir_turns_created
                ON vezir_turns(created_at DESC);

                CREATE TABLE IF NOT EXISTS vezir_learning_snapshots(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    snapshot_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_vezir_learning_key
                ON vezir_learning_snapshots(snapshot_key, created_at DESC);
                """
            )
            con.commit()
        finally:
            con.close()

    @staticmethod
    def _clip(value: Any, limit: int = MAX_MEMORY_TEXT) -> str:
        text = " ".join(str(value or "").split())
        return text[:limit]

    def remember_turn(
        self,
        *,
        question: str,
        answer: str,
        intent: str | None,
        ai_used: bool,
        provider: str | None,
        truth: dict[str, Any],
    ) -> None:
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO vezir_turns(
                    created_at, question, answer, intent,
                    ai_used, provider, truth_json
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    time.time(),
                    self._clip(question, 500),
                    self._clip(answer, 1200),
                    self._clip(intent, 64) or None,
                    1 if ai_used else 0,
                    self._clip(provider, 64) or None,
                    json.dumps(truth, ensure_ascii=False, separators=(",", ":"))[:6000],
                ),
            )
            con.commit()
        finally:
            con.close()

    def recent_turns(self, limit: int = MAX_RECENT_TURNS) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), MAX_RECENT_TURNS))
        con = self._connect()
        try:
            rows = con.execute(
                """
                SELECT question, answer, intent, created_at
                FROM vezir_turns
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            con.close()

        return [
            {
                "question": self._clip(row["question"], 300),
                "answer": self._clip(row["answer"], 500),
                "intent": row["intent"],
                "created_at": row["created_at"],
            }
            for row in reversed(rows)
        ]

    def remember_learning_snapshot(
        self,
        snapshot_key: str,
        payload: dict[str, Any],
    ) -> None:
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO vezir_learning_snapshots(
                    created_at, snapshot_key, payload_json
                ) VALUES(?,?,?)
                """,
                (
                    time.time(),
                    self._clip(snapshot_key, 80),
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:6000],
                ),
            )
            con.commit()
        finally:
            con.close()

    def latest_learning_snapshot(self, snapshot_key: str) -> dict[str, Any] | None:
        con = self._connect()
        try:
            row = con.execute(
                """
                SELECT payload_json
                FROM vezir_learning_snapshots
                WHERE snapshot_key=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (self._clip(snapshot_key, 80),),
            ).fetchone()
        finally:
            con.close()

        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    def status(self) -> dict[str, Any]:
        con = self._connect()
        try:
            turns = int(con.execute("SELECT COUNT(*) FROM vezir_turns").fetchone()[0])
            snapshots = int(con.execute("SELECT COUNT(*) FROM vezir_learning_snapshots").fetchone()[0])
        finally:
            con.close()
        return {
            "state": "READY",
            "turns": turns,
            "learning_snapshots": snapshots,
            "paper_db_write_authority": False,
            "trade_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
