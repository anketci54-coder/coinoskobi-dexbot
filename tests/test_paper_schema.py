import sqlite3

from app.paper.schema import (
    PAPER_SCHEMA_VERSION,
    ensure_paper_schema,
)


REQUIRED_COLUMNS = {
    "id",
    "created_at",
    "closed_at",
    "token",
    "symbol",
    "entry_price",
    "current_price",
    "exit_price",
    "highest_price",
    "lowest_price",
    "tp_price",
    "sl_price",
    "amount_bnb",
    "gross_pnl",
    "net_pnl",
    "roi",
    "gas_buy",
    "gas_sell",
    "swap_fee",
    "buy_tax",
    "sell_tax",
    "slippage",
    "mev",
    "close_reason",
    "status",
    "token_amount",
    "pool",
    "dex",
    "opening_context_json",
}


def test_clean_start_creates_schema(tmp_path):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)

    r = ensure_paper_schema(db)

    assert r["state"] == "READY"

    columns = {
        row[1]
        for row in db.execute(
            "PRAGMA table_info(paper_trades)"
        )
    }

    assert REQUIRED_COLUMNS <= columns

    version = db.execute(
        "PRAGMA user_version"
    ).fetchone()[0]

    assert version == PAPER_SCHEMA_VERSION

    db.close()


def test_schema_is_idempotent(tmp_path):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)

    first = ensure_paper_schema(db)
    second = ensure_paper_schema(db)

    assert first["schema_version"] == PAPER_SCHEMA_VERSION
    assert second["schema_version"] == PAPER_SCHEMA_VERSION

    db.close()


def test_clean_start_supports_insert(tmp_path):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)
    ensure_paper_schema(db)

    db.execute(
        """
        INSERT INTO paper_trades (
            token,
            symbol,
            entry_price,
            current_price,
            highest_price,
            lowest_price,
            tp_price,
            sl_price,
            amount_bnb,
            token_amount,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "0xabc",
            "TEST",
            1.0,
            1.0,
            1.0,
            1.0,
            1.2,
            0.9,
            0.01,
            0.01,
            "OPEN",
        ),
    )

    db.commit()

    row = db.execute(
        """
        SELECT token, status
        FROM paper_trades
        WHERE token=?
        """,
        ("0xabc",),
    ).fetchone()

    assert row == ("0xabc", "OPEN")

    db.close()


def test_required_indexes_created(tmp_path):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)
    ensure_paper_schema(db)

    indexes = {
        row[1]
        for row in db.execute(
            "PRAGMA index_list(paper_trades)"
        )
    }

    assert "idx_paper_trades_token_status" in indexes
    assert "idx_paper_trades_status" in indexes

    db.close()


def test_newer_schema_rejected(tmp_path):
    path = tmp_path / "paper.db"

    db = sqlite3.connect(path)

    db.execute(
        f"PRAGMA user_version={PAPER_SCHEMA_VERSION + 1}"
    )

    try:
        ensure_paper_schema(db)
    except RuntimeError as exc:
        assert "newer than application" in str(exc)
    else:
        raise AssertionError(
            "newer schema must be rejected"
        )

    db.close()
