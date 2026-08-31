import sqlite3
import threading
import time
from pathlib import Path


class WatchProbeStore:
    ENTRY_USDT = 1.0

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()

        self._db = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False,
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA busy_timeout=30000;")

        self._ensure_schema()

    def _ensure_schema(self):
        with self._lock:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_probe_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    token TEXT NOT NULL,
                    pool TEXT NOT NULL,

                    opened_at REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_usdt REAL NOT NULL DEFAULT 1.0,
                    token_amount REAL NOT NULL,

                    last_observed_at REAL,
                    last_price REAL,

                    max_price REAL,
                    min_price REAL,

                    status TEXT NOT NULL DEFAULT 'OPEN',

                    decision_history_id INTEGER,

                    UNIQUE(token, pool)
                )
                """
            )

            self._db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_watch_probe_trades_status
                ON watch_probe_trades(status)
                """
            )

            self._db.commit()

    @staticmethod
    def _canonical(value):
        value = str(value or "").strip().lower()
        return value or None

    @staticmethod
    def _positive_float(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        if value <= 0:
            return None

        return value

    def open_probe(
        self,
        *,
        token,
        pool,
        entry_price,
        opened_at=None,
        decision_history_id=None,
    ):
        token = self._canonical(token)
        pool = self._canonical(pool)
        price = self._positive_float(entry_price)

        if not token or not pool or price is None:
            return {
                "state": "INVALID",
                "created": False,
                "id": None,
            }

        now = (
            float(opened_at)
            if opened_at is not None
            else time.time()
        )

        token_amount = self.ENTRY_USDT / price

        with self._lock:
            try:
                cursor = self._db.execute(
                    """
                    INSERT INTO watch_probe_trades(
                        token,
                        pool,
                        opened_at,
                        entry_price,
                        entry_usdt,
                        token_amount,
                        last_observed_at,
                        last_price,
                        max_price,
                        min_price,
                        status,
                        decision_history_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        token,
                        pool,
                        now,
                        price,
                        self.ENTRY_USDT,
                        token_amount,
                        now,
                        price,
                        price,
                        price,
                        "OPEN",
                        decision_history_id,
                    ),
                )

                self._db.commit()

                return {
                    "state": "OPENED",
                    "created": True,
                    "id": int(cursor.lastrowid),
                    "entry_usdt": self.ENTRY_USDT,
                    "token_amount": token_amount,
                }

            except sqlite3.IntegrityError:
                self._db.rollback()

                row = self._db.execute(
                    """
                    SELECT id
                    FROM watch_probe_trades
                    WHERE lower(token)=lower(?)
                      AND lower(pool)=lower(?)
                    LIMIT 1
                    """,
                    (token, pool),
                ).fetchone()

                return {
                    "state": "ALREADY_EXISTS",
                    "created": False,
                    "id": (
                        int(row["id"])
                        if row is not None
                        else None
                    ),
                }

    def observe(
        self,
        *,
        token,
        current_price,
        observed_at=None,
    ):
        token = self._canonical(token)
        price = self._positive_float(current_price)

        if not token or price is None:
            return {
                "state": "INVALID",
                "updated": 0,
            }

        now = (
            float(observed_at)
            if observed_at is not None
            else time.time()
        )

        with self._lock:
            rows = self._db.execute(
                """
                SELECT id, max_price, min_price
                FROM watch_probe_trades
                WHERE lower(token)=lower(?)
                  AND status='OPEN'
                """,
                (token,),
            ).fetchall()

            updated = 0

            for row in rows:
                max_price = max(
                    float(row["max_price"] or price),
                    price,
                )
                min_price = min(
                    float(row["min_price"] or price),
                    price,
                )

                self._db.execute(
                    """
                    UPDATE watch_probe_trades
                    SET
                        last_observed_at=?,
                        last_price=?,
                        max_price=?,
                        min_price=?
                    WHERE id=?
                    """,
                    (
                        now,
                        price,
                        max_price,
                        min_price,
                        int(row["id"]),
                    ),
                )

                updated += 1

            self._db.commit()

        return {
            "state": "OBSERVED",
            "updated": updated,
        }

    def snapshot(self, limit=20):
        with self._lock:
            rows = self._db.execute(
                """
                SELECT *
                FROM watch_probe_trades
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

        return [dict(row) for row in rows]
