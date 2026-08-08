from app.paper.database import PaperDatabase

def test_database():
    db = PaperDatabase()

    assert db is PaperDatabase()
    assert db.conn.execute(
        "PRAGMA journal_mode"
    ).fetchone()[0].lower() == "wal"

    assert db.conn.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0] == 1
