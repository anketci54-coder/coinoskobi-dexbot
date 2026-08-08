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
