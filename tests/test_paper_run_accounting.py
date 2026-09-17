import sqlite3

import pytest

from app.paper.schema import ensure_paper_schema
from app.risk.paper_position_sizing import (
    paper_available_capital_usdt,
)


def _db():
    db = sqlite3.connect(":memory:")
    ensure_paper_schema(db)
    return db


def _insert_trade(
    db,
    *,
    status,
    entry_amount=0.0,
    remaining_basis=0.0,
    realized_pnl=0.0,
    net_pnl=0.0,
):
    db.execute(
        """
        INSERT INTO paper_trades (
            status,
            paper_account_version,
            entry_amount_usdt,
            remaining_cost_basis_usdt,
            realized_pnl_usdt,
            net_pnl_usdt
        )
        VALUES (?, 'PAPER_10K_V2', ?, ?, ?, ?)
        """,
        (
            status,
            entry_amount,
            remaining_basis,
            realized_pnl,
            net_pnl,
        ),
    )
    db.commit()


def _start_run(db, capital=10000.0):
    boundary = db.execute(
        "SELECT COALESCE(MAX(id),0) FROM paper_trades"
    ).fetchone()[0]

    db.execute(
        """
        INSERT INTO paper_runs (
            run_key,
            started_at,
            starting_capital_usdt,
            start_trade_id,
            start_realization_id,
            start_candidate_id,
            status,
            metadata_json
        )
        VALUES (
            'TEST_RUN',
            1.0,
            ?,
            ?,
            0,
            0,
            'ACTIVE',
            '{}'
        )
        """,
        (capital, boundary),
    )
    db.commit()


def test_active_run_ignores_all_historical_pnl():
    db = _db()

    _insert_trade(
        db,
        status="CLOSED",
        net_pnl=-5000.0,
    )
    _insert_trade(
        db,
        status="CLOSED",
        net_pnl=2500.0,
    )

    _start_run(db)

    assert (
        paper_available_capital_usdt(db)
        == pytest.approx(10000.0)
    )


def test_new_closed_trade_changes_only_current_run():
    db = _db()

    _insert_trade(
        db,
        status="CLOSED",
        net_pnl=-5000.0,
    )

    _start_run(db)

    _insert_trade(
        db,
        status="CLOSED",
        net_pnl=125.0,
    )

    assert (
        paper_available_capital_usdt(db)
        == pytest.approx(10125.0)
    )


def test_new_open_position_reserves_current_run_cash():
    db = _db()
    _start_run(db)

    _insert_trade(
        db,
        status="OPEN",
        entry_amount=400.0,
        remaining_basis=400.0,
    )

    assert (
        paper_available_capital_usdt(db)
        == pytest.approx(9600.0)
    )


def test_partial_realized_pnl_counts_while_basis_remains_reserved():
    db = _db()
    _start_run(db)

    _insert_trade(
        db,
        status="OPEN",
        entry_amount=400.0,
        remaining_basis=200.0,
        realized_pnl=50.0,
    )

    assert (
        paper_available_capital_usdt(db)
        == pytest.approx(9850.0)
    )


def test_no_run_preserves_legacy_accounting_behavior():
    db = _db()

    _insert_trade(
        db,
        status="CLOSED",
        net_pnl=50.0,
    )

    assert (
        paper_available_capital_usdt(
            db,
            10000.0,
        )
        == pytest.approx(10050.0)
    )
