import sqlite3
import threading

from app.paper.database import PaperDatabase
from app.risk.paper_position_sizing import (
    paper_available_capital_usdt,
)


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
            created_at TEXT,
            paper_account_version TEXT,
            entry_amount_usdt REAL,
            remaining_cost_basis_usdt REAL,
            realized_pnl_usdt REAL,
            net_pnl_usdt REAL,
            net_pnl REAL
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


def test_closed_token_cannot_open_second_trade():
    db = make_db()

    assert db.insert_if_below_open_limit(
        {"token": "0xsingle", "status": "OPEN"},
        30,
    ) is True

    db.conn.execute(
        """
        UPDATE paper_trades
        SET status='CLOSED'
        WHERE lower(token)=lower(?)
        """,
        ("0xsingle",),
    )
    db.conn.commit()

    assert db.has_open_position(
        "0xsingle"
    ) is False
    assert db.has_trade_history(
        "0xsingle"
    ) is True

    assert db.insert_if_below_open_limit(
        {"token": "0xsingle", "status": "OPEN"},
        30,
    ) is False

    count = db.conn.execute(
        """
        SELECT COUNT(*)
        FROM paper_trades
        WHERE lower(token)=lower(?)
        """,
        ("0xsingle",),
    ).fetchone()[0]

    assert count == 1


def test_available_capital_uses_realized_account_truth():
    db = make_db()

    db.conn.execute(
        """
        INSERT INTO paper_trades(
            token,
            status,
            paper_account_version,
            entry_amount_usdt,
            remaining_cost_basis_usdt,
            realized_pnl_usdt,
            net_pnl_usdt,
            net_pnl
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "0xclosed",
            "CLOSED",
            "PAPER_10K_V2",
            1000.0,
            0.0,
            -1000.0,
            -1000.0,
            -1000.0,
        ),
    )

    db.conn.execute(
        """
        INSERT INTO paper_trades(
            token,
            status,
            paper_account_version,
            entry_amount_usdt,
            remaining_cost_basis_usdt,
            realized_pnl_usdt,
            net_pnl_usdt,
            net_pnl
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "0xopen",
            "OPEN",
            "PAPER_10K_V2",
            2000.0,
            1200.0,
            100.0,
            0.0,
            0.0,
        ),
    )

    db.conn.commit()

    assert (
        paper_available_capital_usdt(
            db.conn
        )
        == 7900.0
    )


def test_atomic_insert_rejects_entry_above_real_free_capital():
    db = make_db()

    db.conn.execute(
        """
        INSERT INTO paper_trades(
            token,
            status,
            paper_account_version,
            entry_amount_usdt,
            remaining_cost_basis_usdt,
            realized_pnl_usdt,
            net_pnl_usdt,
            net_pnl
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "0xloss",
            "CLOSED",
            "PAPER_10K_V2",
            8000.0,
            0.0,
            -8000.0,
            -8000.0,
            -8000.0,
        ),
    )

    db.conn.commit()

    assert (
        paper_available_capital_usdt(
            db.conn
        )
        == 2000.0
    )

    assert db.insert_if_below_open_limit(
        {
            "token": "0xtoo-big",
            "status": "OPEN",
            "paper_account_version": (
                "PAPER_10K_V2"
            ),
            "entry_amount_usdt": 2500.0,
            "remaining_cost_basis_usdt": 2500.0,
            "realized_pnl_usdt": 0.0,
        },
        30,
    ) is False

    assert db.insert_if_below_open_limit(
        {
            "token": "0xfits",
            "status": "OPEN",
            "paper_account_version": (
                "PAPER_10K_V2"
            ),
            "entry_amount_usdt": 1500.0,
            "remaining_cost_basis_usdt": 1500.0,
            "realized_pnl_usdt": 0.0,
        },
        30,
    ) is True

    assert (
        paper_available_capital_usdt(
            db.conn
        )
        == 500.0
    )
