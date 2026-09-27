import sqlite3
from datetime import datetime, timezone

from app.paper.database import PaperDatabase
from app.paper.schema import ensure_paper_schema


def _database():
    db = object.__new__(PaperDatabase)
    db.conn = sqlite3.connect(":memory:")
    ensure_paper_schema(db.conn)
    return db


def test_insert_assigns_real_created_at_when_missing():
    db = _database()
    before = datetime.now(timezone.utc)

    db._insert_unlocked({
        "token": "0xtoken",
        "status": "OPEN",
    })

    created = db.conn.execute("SELECT created_at FROM paper_trades").fetchone()[0]
    assert before <= datetime.fromisoformat(created) <= datetime.now(timezone.utc)
    db.conn.close()


def test_insert_preserves_explicit_created_at():
    db = _database()

    timestamp = "2026-08-14T00:00:00+00:00"

    db._insert_unlocked({
        "token": "0xtoken",
        "status": "OPEN",
        "created_at": timestamp,
    })

    assert db.conn.execute("SELECT created_at FROM paper_trades").fetchone()[0] == timestamp
    db.conn.close()
