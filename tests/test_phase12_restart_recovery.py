import importlib
import sqlite3
from pathlib import Path

from app.paper.schema import PAPER_SCHEMA_VERSION, ensure_paper_schema


def test_application_can_be_built_repeatedly(monkeypatch):
    module = importlib.import_module("main")
    monkeypatch.setattr(module, "WSS_URL", "")
    monkeypatch.setattr(module, "WSS_PAIR", "")
    for _ in range(25):
        app = module.build_application()
        assert app["pipeline"] is not None
        assert app["runner"] is not None


def test_schema_reopen_preserves_version(tmp_path):
    path = tmp_path / "restart.db"
    for _ in range(2):
        db = sqlite3.connect(path)
        ensure_paper_schema(db)
        db.close()
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == PAPER_SCHEMA_VERSION
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    db.close()


def test_repeated_schema_restart(tmp_path):
    path = tmp_path / "repeat.db"
    for _ in range(50):
        db = sqlite3.connect(path)
        ensure_paper_schema(db)
        db.close()
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    db.close()


def test_existing_real_database_readonly_health():
    path = Path("data/paper_trades.db")
    assert path.exists()
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    assert db.execute("PRAGMA user_version").fetchone()[0] == PAPER_SCHEMA_VERSION
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    duplicates = db.execute("""
        SELECT lower(token), COUNT(*)
        FROM paper_trades
        WHERE status='OPEN'
          AND token IS NOT NULL
        GROUP BY lower(token)
        HAVING COUNT(*) > 1
    """).fetchall()
    db.close()
    assert duplicates == []
