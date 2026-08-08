import sqlite3
from pathlib import Path

DB = Path("data/paper_trades.db")


class PaperDatabase:

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):

        if self.__class__._initialized:
            return

        DB.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            DB,
            timeout=30,
            check_same_thread=False,
        )

        self.conn.row_factory = sqlite3.Row

        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.conn.execute("PRAGMA busy_timeout=30000;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")

        self.__class__._initialized = True

    def has_open_position(self, token):

        row = self.conn.execute(
            """
            SELECT 1
            FROM paper_trades
            WHERE token=?
              AND status='OPEN'
            LIMIT 1
            """,
            (token,),
        ).fetchone()

        return row is not None

    def insert(self, trade):

        cols = ",".join(trade.keys())
        vals = ",".join("?" * len(trade))

        self.conn.execute(
            f"INSERT INTO paper_trades ({cols}) VALUES ({vals})",
            tuple(trade.values()),
        )

        self.conn.commit()

    def open_positions(self):

        cur = self.conn.execute(
            """
            SELECT *
            FROM paper_trades
            WHERE status='OPEN'
            ORDER BY id
            """
        )

        return [dict(r) for r in cur.fetchall()]

    def update_position(self, trade_id, values):

        sql = ",".join(f"{k}=?" for k in values)

        params = list(values.values())
        params.append(trade_id)

        self.conn.execute(
            f"""
            UPDATE paper_trades
               SET {sql}
             WHERE id=?
            """,
            params,
        )

        self.conn.commit()

    def close_position(self, trade_id, values=None):

        values = values or {}
        values["status"] = "CLOSED"

        self.update_position(trade_id, values)
