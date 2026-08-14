import sqlite3
import threading

from app.paper.database import PaperDatabase


def make_db():
    db = object.__new__(PaperDatabase)
    db.conn = sqlite3.connect(
        ":memory:",
        check_same_thread=False,
    )
    db.conn.row_factory = sqlite3.Row
    db._db_lock = threading.RLock()
    db.conn.execute("""
        CREATE TABLE paper_trades(
            id INTEGER PRIMARY KEY,
            token TEXT,
            status TEXT,
            created_at TEXT
        )
    """)
    return db


def test_atomic_open_position_cap():
    db = make_db()

    assert db.insert_if_below_open_limit(
        {"token": "0xtoken1", "status": "OPEN"},
        1,
    ) is True

    assert db.insert_if_below_open_limit(
        {"token": "0xtoken2", "status": "OPEN"},
        1,
    ) is False

    count = db.conn.execute("""
        SELECT COUNT(*)
        FROM paper_trades
        WHERE status='OPEN'
    """).fetchone()[0]

    assert count == 1


def test_atomic_cap_rejects_duplicate_token():
    db = make_db()

    assert db.insert_if_below_open_limit(
        {"token": "0xtoken", "status": "OPEN"},
        30,
    ) is True

    assert db.insert_if_below_open_limit(
        {"token": "0xtoken", "status": "OPEN"},
        30,
    ) is False
