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

            # Additive V2 migration only.
            # Existing WATCH probe rows remain canonical and untouched.
            columns = {
                row["name"]
                for row in self._db.execute(
                    "PRAGMA table_info(watch_probe_trades)"
                ).fetchall()
            }

            additions = {
                "mark_return_pct": "REAL",
                "mfe_pct": "REAL",
                "mae_pct": "REAL",
                "peak_drawdown_pct": "REAL",
                "realizable_exit_usdt": "REAL",
                "realizable_return_pct": "REAL",
                "exit_state": "TEXT NOT NULL DEFAULT 'UNVERIFIED'",
                "exit_quality": "TEXT",
                "exit_reason": "TEXT",
                "closed_at": "REAL",
                "last_exit_probe_at": "REAL",
                "context_version": "TEXT",
            }

            for name, declaration in additions.items():
                if name not in columns:
                    self._db.execute(
                        f"ALTER TABLE watch_probe_trades "
                        f"ADD COLUMN {name} {declaration}"
                    )

            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_probe_shadow_exits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_id INTEGER NOT NULL,
                    strategy TEXT NOT NULL,
                    triggered_at REAL,
                    trigger_price REAL,
                    return_pct REAL,
                    state TEXT NOT NULL DEFAULT 'ARMED',
                    reason TEXT,
                    UNIQUE(probe_id, strategy)
                )
                """
            )

            self._db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_watch_probe_shadow_exits_probe
                ON watch_probe_shadow_exits(probe_id)
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

        if (
            not token
            or not pool
            or token == pool
            or price is None
        ):
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

    def _ensure_shadow_exit_rows(self, probe_id):
        strategies = (
            "TP_2X",
            "TP_5X",
            "TRAIL_25",
            "TIME_60M",
            "TIME_6H",
        )

        for strategy in strategies:
            self._db.execute(
                """
                INSERT OR IGNORE INTO watch_probe_shadow_exits(
                    probe_id,
                    strategy
                )
                VALUES(?,?)
                """,
                (
                    int(probe_id),
                    strategy,
                ),
            )

    def _update_shadow_exits(
        self,
        *,
        row,
        price,
        observed_at,
        max_price,
    ):
        probe_id = int(row["id"])
        entry_price = float(row["entry_price"])
        opened_at = float(row["opened_at"])

        self._ensure_shadow_exit_rows(probe_id)

        elapsed = float(observed_at) - opened_at
        mark_return_pct = (
            (float(price) / entry_price) - 1.0
        ) * 100.0

        drawdown_from_peak_pct = (
            (float(price) / float(max_price)) - 1.0
        ) * 100.0

        rules = {
            "TP_2X": (
                mark_return_pct >= 100.0,
                "TARGET_2X",
            ),
            "TP_5X": (
                mark_return_pct >= 400.0,
                "TARGET_5X",
            ),
            "TRAIL_25": (
                max_price > entry_price
                and drawdown_from_peak_pct <= -25.0,
                "PEAK_DRAWDOWN_25",
            ),
            "TIME_60M": (
                elapsed >= 3600.0,
                "TIME_60M",
            ),
            "TIME_6H": (
                elapsed >= 21600.0,
                "TIME_6H",
            ),
        }

        for strategy, (triggered, reason) in rules.items():
            if not triggered:
                continue

            existing = self._db.execute(
                """
                SELECT state
                FROM watch_probe_shadow_exits
                WHERE probe_id=? AND strategy=?
                """,
                (
                    probe_id,
                    strategy,
                ),
            ).fetchone()

            if (
                existing is None
                or existing["state"] == "TRIGGERED"
            ):
                continue

            self._db.execute(
                """
                UPDATE watch_probe_shadow_exits
                SET
                    triggered_at=?,
                    trigger_price=?,
                    return_pct=?,
                    state='TRIGGERED',
                    reason=?
                WHERE probe_id=?
                  AND strategy=?
                """,
                (
                    float(observed_at),
                    float(price),
                    mark_return_pct,
                    reason,
                    probe_id,
                    strategy,
                ),
            )

    def observe(
        self,
        *,
        token,
        pool,
        current_price,
        observed_at=None,
    ):
        token = self._canonical(token)
        pool = self._canonical(pool)
        price = self._positive_float(current_price)

        if (
            not token
            or not pool
            or token == pool
            or price is None
        ):
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
                SELECT
                    id,
                    opened_at,
                    entry_price,
                    max_price,
                    min_price
                FROM watch_probe_trades
                WHERE lower(token)=lower(?)
                  AND lower(pool)=lower(?)
                  AND status='OPEN'
                """,
                (token, pool),
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

                entry_price = float(
                    row["entry_price"]
                )

                mark_return_pct = (
                    (price / entry_price) - 1.0
                ) * 100.0

                mfe_pct = (
                    (max_price / entry_price) - 1.0
                ) * 100.0

                mae_pct = (
                    (min_price / entry_price) - 1.0
                ) * 100.0

                peak_drawdown_pct = (
                    (price / max_price) - 1.0
                ) * 100.0

                self._update_shadow_exits(
                    row=row,
                    price=price,
                    observed_at=now,
                    max_price=max_price,
                )

                self._db.execute(
                    """
                    UPDATE watch_probe_trades
                    SET
                        last_observed_at=?,
                        last_price=?,
                        max_price=?,
                        min_price=?,
                        mark_return_pct=?,
                        mfe_pct=?,
                        mae_pct=?,
                        peak_drawdown_pct=?
                    WHERE id=?
                    """,
                    (
                        now,
                        price,
                        max_price,
                        min_price,
                        mark_return_pct,
                        mfe_pct,
                        mae_pct,
                        peak_drawdown_pct,
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
