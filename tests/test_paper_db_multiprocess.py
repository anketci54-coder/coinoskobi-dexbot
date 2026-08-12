import multiprocessing
import sqlite3

from app.paper.schema import (
    ensure_paper_schema,
)


def _attempt_open(
    path,
    token,
    start,
    output,
):
    db = sqlite3.connect(
        path,
        timeout=30,
    )

    db.execute(
        "PRAGMA busy_timeout=30000"
    )

    start.wait()

    try:
        db.execute(
            """
            INSERT INTO paper_trades(
                token,
                status
            )
            VALUES (?, 'OPEN')
            """,
            (token,),
        )

        db.commit()
        output.put("INSERTED")

    except sqlite3.IntegrityError:
        db.rollback()
        output.put("REJECTED")

    finally:
        db.close()


def test_only_one_process_can_create_open_position(
    tmp_path,
):
    path = str(
        tmp_path / "paper.db"
    )

    db = sqlite3.connect(path)

    db.execute(
        "PRAGMA journal_mode=WAL"
    )

    db.execute(
        "PRAGMA busy_timeout=30000"
    )

    ensure_paper_schema(db)
    db.close()

    ctx = multiprocessing.get_context(
        "spawn"
    )

    start = ctx.Event()
    output = ctx.Queue()

    processes = [
        ctx.Process(
            target=_attempt_open,
            args=(
                path,
                "0xAbC",
                start,
                output,
            ),
        )
        for _ in range(8)
    ]

    for process in processes:
        process.start()

    start.set()

    for process in processes:
        process.join(30)

        assert (
            process.exitcode == 0
        )

    results = [
        output.get(timeout=5)
        for _ in processes
    ]

    assert (
        results.count("INSERTED")
        == 1
    )

    assert (
        results.count("REJECTED")
        == 7
    )

    db = sqlite3.connect(path)

    count = db.execute(
        """
        SELECT COUNT(*)
        FROM paper_trades
        WHERE lower(token)=lower(?)
          AND status='OPEN'
        """,
        ("0xabc",),
    ).fetchone()[0]

    assert count == 1

    assert (
        db.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        == "ok"
    )

    db.close()
