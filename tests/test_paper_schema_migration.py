import sqlite3

import pytest

from app.paper.schema import (
    PAPER_SCHEMA_VERSION,
    ensure_paper_schema,
)


OLD_SCHEMA = """
CREATE TABLE paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    closed_at TEXT,
    token TEXT,
    symbol TEXT,
    entry_price REAL,
    current_price REAL,
    exit_price REAL,
    highest_price REAL,
    lowest_price REAL,
    tp_price REAL,
    sl_price REAL,
    amount_bnb REAL,
    gross_pnl REAL,
    net_pnl REAL,
    roi REAL,
    gas_buy REAL,
    gas_sell REAL,
    swap_fee REAL,
    buy_tax REAL,
    sell_tax REAL,
    slippage REAL,
    mev REAL,
    close_reason TEXT,
    status TEXT,
    token_amount REAL DEFAULT 0,
    pool TEXT,
    dex TEXT
)
"""


def _v1(path):
    db = sqlite3.connect(path)

    db.execute(OLD_SCHEMA)
    db.execute("PRAGMA user_version=1")
    db.commit()

    return db


def _indexes(db):
    return {
        row[1]
        for row in db.execute(
            "PRAGMA index_list(paper_trades)"
        )
    }


def test_v1_clean_database_migrates_to_current(
    tmp_path,
):
    path = tmp_path / "old.db"

    db = _v1(path)

    r = ensure_paper_schema(db)

    assert r["schema_version"] == PAPER_SCHEMA_VERSION
    assert r[
        "single_open_db_enforced"
    ] is True

    version = db.execute(
        "PRAGMA user_version"
    ).fetchone()[0]

    assert (
        version
        == PAPER_SCHEMA_VERSION
    )

    assert (
        "idx_paper_trades_one_open_per_token"
        in _indexes(db)
    )

    db.close()


def test_db_rejects_second_open_same_token(
    tmp_path,
):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)
    ensure_paper_schema(db)

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES (?, 'OPEN')
        """,
        ("0xabc",),
    )

    db.commit()

    with pytest.raises(
        sqlite3.IntegrityError
    ):
        db.execute(
            """
            INSERT INTO paper_trades(
                token,
                status
            )
            VALUES (?, 'OPEN')
            """,
            ("0xabc",),
        )

    db.rollback()
    db.close()


def test_open_uniqueness_is_case_insensitive(
    tmp_path,
):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)
    ensure_paper_schema(db)

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES (?, 'OPEN')
        """,
        ("0xAbC",),
    )

    db.commit()

    with pytest.raises(
        sqlite3.IntegrityError
    ):
        db.execute(
            """
            INSERT INTO paper_trades(
                token,
                status
            )
            VALUES (?, 'OPEN')
            """,
            ("0xabc",),
        )

    db.rollback()
    db.close()


def test_closed_history_does_not_block_new_open(
    tmp_path,
):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)
    ensure_paper_schema(db)

    for _ in range(3):
        db.execute(
            """
            INSERT INTO paper_trades(
                token,
                status
            )
            VALUES (?, 'CLOSED')
            """,
            ("0xabc",),
        )

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES (?, 'OPEN')
        """,
        ("0xabc",),
    )

    db.commit()

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

    db.close()


def test_migration_refuses_legacy_duplicate_open(
    tmp_path,
):
    path = tmp_path / "bad-old.db"

    db = _v1(path)

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES ('0xabc', 'OPEN')
        """
    )

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES ('0xAbC', 'OPEN')
        """
    )

    db.commit()

    with pytest.raises(
        RuntimeError,
        match="duplicate OPEN positions",
    ):
        ensure_paper_schema(db)

    version = db.execute(
        "PRAGMA user_version"
    ).fetchone()[0]

    assert version == 1

    assert (
        "idx_paper_trades_one_open_per_token"
        not in _indexes(db)
    )

    rows = db.execute(
        """
        SELECT COUNT(*)
        FROM paper_trades
        WHERE status='OPEN'
        """
    ).fetchone()[0]

    assert rows == 2

    db.close()


def test_migration_is_idempotent(
    tmp_path,
):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)

    first = ensure_paper_schema(db)
    second = ensure_paper_schema(db)

    assert first["schema_version"] == PAPER_SCHEMA_VERSION
    assert second["schema_version"] == PAPER_SCHEMA_VERSION

    indexes = _indexes(db)

    assert (
        "idx_paper_trades_one_open_per_token"
        in indexes
    )

    db.close()


def test_newer_schema_still_rejected(
    tmp_path,
):
    path = tmp_path / "future.db"

    db = sqlite3.connect(path)

    db.execute(
        f"PRAGMA user_version="
        f"{PAPER_SCHEMA_VERSION + 1}"
    )

    db.commit()

    with pytest.raises(
        RuntimeError,
        match="newer than application",
    ):
        ensure_paper_schema(db)

    db.close()

def test_existing_schema_gains_trade_policy_without_rewriting_history(
    tmp_path,
):
    path = tmp_path / "policy-old.db"

    db = _v1(path)

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES ('0xabc', 'CLOSED')
        """
    )
    db.commit()

    ensure_paper_schema(db)

    columns = {
        row[1]
        for row in db.execute(
            "PRAGMA table_info(paper_trades)"
        )
    }

    assert "trade_policy" in columns

    row = db.execute(
        """
        SELECT token, status, trade_policy
        FROM paper_trades
        WHERE token='0xabc'
        """
    ).fetchone()

    assert row == (
        "0xabc",
        "CLOSED",
        None,
    )

    db.close()


def test_existing_open_position_preserves_legacy_vur_kac_lifecycle(
    tmp_path,
):
    path = tmp_path / "legacy-open-policy.db"

    db = _v1(path)

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES ('0xlegacy', 'OPEN')
        """
    )

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status
        )
        VALUES ('0xhistory', 'CLOSED')
        """
    )

    db.commit()

    ensure_paper_schema(db)

    opened = db.execute(
        """
        SELECT trade_policy
        FROM paper_trades
        WHERE token='0xlegacy'
        """
    ).fetchone()[0]

    closed = db.execute(
        """
        SELECT trade_policy
        FROM paper_trades
        WHERE token='0xhistory'
        """
    ).fetchone()[0]

    assert opened == "VUR_KAC"
    assert closed is None

    db.close()
