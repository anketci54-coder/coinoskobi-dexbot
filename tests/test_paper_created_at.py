from app.paper.database import PaperDatabase


class Connection:
    def __init__(self):
        self.sql = None
        self.values = None

    def execute(self, sql, values):
        self.sql = sql
        self.values = values


def test_insert_assigns_real_created_at_when_missing():
    db = object.__new__(PaperDatabase)
    db.conn = Connection()

    db._insert_unlocked({
        "token": "0xtoken",
        "status": "OPEN",
    })

    assert "created_at" in db.conn.sql
    assert db.conn.values[-1]
    assert "+00:00" in db.conn.values[-1]


def test_insert_preserves_explicit_created_at():
    db = object.__new__(PaperDatabase)
    db.conn = Connection()

    timestamp = "2026-08-14T00:00:00+00:00"

    db._insert_unlocked({
        "token": "0xtoken",
        "status": "OPEN",
        "created_at": timestamp,
    })

    assert db.conn.values[-1] == timestamp
