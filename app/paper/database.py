import sqlite3
import threading
from pathlib import Path

from app.paper.schema import ensure_paper_schema

DB = Path("data/paper_trades.db")


class PaperDatabase:

    _instance = None
    _initialized = False
    _db_lock = threading.RLock()

    def __new__(cls):
        with cls._db_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        with self._db_lock:
            if self.__class__._initialized:
                return

            DB.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(DB, timeout=30, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA foreign_keys=ON;")
            self.conn.execute("PRAGMA busy_timeout=30000;")
            self.conn.execute("PRAGMA synchronous=NORMAL;")
            ensure_paper_schema(self.conn)
            self.__class__._initialized = True

    def has_open_position(self, token):
        with self._db_lock:
            row = self.conn.execute(
                "SELECT 1 FROM paper_trades WHERE lower(token)=lower(?) AND status='OPEN' LIMIT 1",
                (token,),
            ).fetchone()
            return row is not None

    def insert(self, trade):
        with self._db_lock:
            self._insert_unlocked(trade)
            self.conn.commit()

    def insert_if_no_open_position(self, trade):
        token = (trade or {}).get("token")
        if not token:
            raise ValueError("trade token is required")

        with self._db_lock:
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                row = self.conn.execute(
                    "SELECT 1 FROM paper_trades WHERE lower(token)=lower(?) AND status='OPEN' LIMIT 1",
                    (token,),
                ).fetchone()
                if row is not None:
                    self.conn.rollback()
                    return False
                self._insert_unlocked(trade)
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                self.conn.rollback()
                row = self.conn.execute(
                    "SELECT 1 FROM paper_trades WHERE lower(token)=lower(?) AND status='OPEN' LIMIT 1",
                    (token,),
                ).fetchone()
                if row is not None:
                    return False
                raise
            except Exception:
                self.conn.rollback()
                raise

    def _insert_unlocked(self, trade):
        cols = ",".join(trade.keys())
        vals = ",".join("?" * len(trade))
        self.conn.execute(
            f"INSERT INTO paper_trades ({cols}) VALUES ({vals})",
            tuple(trade.values()),
        )

    def open_positions(self):
        with self._db_lock:
            cur = self.conn.execute(
                "SELECT * FROM paper_trades WHERE status='OPEN' ORDER BY id"
            )
            return [dict(r) for r in cur.fetchall()]

    def closed_positions(self, after_id=0):
        """Durable CLOSED rows for bounded/idempotent learning replay."""
        with self._db_lock:
            cur = self.conn.execute(
                "SELECT * FROM paper_trades WHERE status='CLOSED' AND id > ? ORDER BY id",
                (int(after_id or 0),),
            )
            return [dict(r) for r in cur.fetchall()]

    def update_position(self, trade_id, values):
        with self._db_lock:
            sql = ",".join(f"{k}=?" for k in values)
            params = list(values.values())
            params.append(trade_id)
            self.conn.execute(
                f"UPDATE paper_trades SET {sql} WHERE id=?",
                params,
            )
            self.conn.commit()

    def close_position(self, trade_id, values=None):
        """Idempotent OPEN -> CLOSED transition; returns True only once."""
        values = dict(values or {})
        values["status"] = "CLOSED"
        with self._db_lock:
            sql = ",".join(f"{k}=?" for k in values)
            params = list(values.values())
            params.append(trade_id)
            cur = self.conn.execute(
                f"UPDATE paper_trades SET {sql} WHERE id=? AND status='OPEN'",
                params,
            )
            self.conn.commit()
            return cur.rowcount == 1
