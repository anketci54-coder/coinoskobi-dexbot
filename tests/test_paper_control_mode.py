import sqlite3
from pathlib import Path

from app.paper.control_mode import (
    auto_entry_enabled,
    get_control_mode,
    set_control_mode,
)


def test_default_control_mode_is_auto(
    tmp_path: Path,
):
    db = tmp_path / "paper.db"

    assert get_control_mode(db) == "AUTO"
    assert auto_entry_enabled(db) is True


def test_manual_mode_disables_only_auto_entry(
    tmp_path: Path,
):
    db = tmp_path / "paper.db"

    assert (
        set_control_mode(
            db,
            "MANUAL",
        )
        == "MANUAL"
    )

    assert get_control_mode(db) == "MANUAL"
    assert auto_entry_enabled(db) is False


def test_mode_change_does_not_mutate_positions(
    tmp_path: Path,
):
    db = tmp_path / "paper.db"

    con = sqlite3.connect(db)

    con.execute(
        """
        CREATE TABLE paper_trades(
            id INTEGER PRIMARY KEY,
            control_mode TEXT,
            trade_type TEXT,
            sl_price REAL,
            tp_price REAL,
            mathematical_plan_json TEXT
        )
        """
    )

    con.execute(
        """
        INSERT INTO paper_trades(
            id,
            control_mode,
            trade_type,
            sl_price,
            tp_price,
            mathematical_plan_json
        )
        VALUES(
            1,
            'AUTO',
            'NORMAL',
            9.0,
            12.0,
            '{"contract":"mathematical_trade_plan"}'
        )
        """
    )

    con.commit()
    con.close()

    set_control_mode(
        db,
        "MANUAL",
    )

    con = sqlite3.connect(db)
    row = con.execute(
        """
        SELECT
            control_mode,
            trade_type,
            sl_price,
            tp_price,
            mathematical_plan_json
        FROM paper_trades
        WHERE id=1
        """
    ).fetchone()
    con.close()

    assert row == (
        "AUTO",
        "NORMAL",
        9.0,
        12.0,
        '{"contract":"mathematical_trade_plan"}',
    )
