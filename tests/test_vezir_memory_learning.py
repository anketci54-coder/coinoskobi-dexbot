import sqlite3

from app.api.vezir_learning import watch_learning_snapshot
from app.api.vezir_memory import VezirMemoryStore
from app.learning.watch_probe_store import WatchProbeStore


def test_vezir_memory_is_separate_and_bounded(tmp_path):
    db = tmp_path / "vezir.db"
    memory = VezirMemoryStore(db)
    for i in range(12):
        memory.remember_turn(
            question=f"q{i}",
            answer=f"a{i}",
            intent="SYSTEM",
            ai_used=True,
            provider="GROQ",
            truth={"n": i},
        )
    rows = memory.recent_turns(99)
    assert len(rows) == 8
    assert rows[0]["question"] == "q4"
    status = memory.status()
    assert status["turns"] == 12
    assert status["paper_db_write_authority"] is False
    assert status["trade_authority"] is False
    assert status["wallet_authority"] is False
    assert status["signing_authority"] is False
    assert status["execution_authority"] is False


def test_watch_learning_uses_only_verified_durable_exits(tmp_path):
    db = tmp_path / "paper.db"
    store = WatchProbeStore(db)
    for i in range(12):
        store.open_probe(
            token=f"0x{i + 100:040x}",
            pool=f"0x{i + 1000:040x}",
            entry_price=1.0,
            opened_at=1000.0 + i,
        )

    con = sqlite3.connect(db)
    rows = con.execute("SELECT id FROM watch_probe_trades ORDER BY id").fetchall()
    for index, (probe_id,) in enumerate(rows):
        if index < 10:
            exit_usdt = 2.0 if index < 6 else 0.5
            con.execute(
                """
                UPDATE watch_probe_trades
                SET status='CLOSED', exit_state='VERIFIED',
                    realizable_exit_usdt=?, last_exit_probe_at=2000
                WHERE id=?
                """,
                (exit_usdt, probe_id),
            )
        elif index == 10:
            con.execute(
                """
                UPDATE watch_probe_trades
                SET exit_state='LIMITED', last_exit_probe_at=2000
                WHERE id=?
                """,
                (probe_id,),
            )
    con.commit()
    con.close()

    snapshot = watch_learning_snapshot(db)
    assert snapshot["total"] == 12
    assert snapshot["closed"] == 10
    assert snapshot["verified"] == 10
    assert snapshot["verified_wins"] == 6
    assert snapshot["verified_win_rate"] == 0.6
    assert snapshot["learning_confidence"] == "LOW"
    assert snapshot["paper_db_write_authority"] is False
    assert snapshot["execution_authority"] is False
