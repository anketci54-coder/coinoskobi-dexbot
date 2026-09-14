import sqlite3

from app.paper.schema import ensure_paper_schema
from app.paper.trade_contract import (
    CONTROL_MODES,
    LEVEL_SOURCES,
    TRADE_TYPES,
    legacy_trade_contract,
    normalize_control_mode,
    normalize_level_source,
    normalize_trade_type,
)


def test_canonical_trade_contract_axes_are_independent():
    assert CONTROL_MODES == {"AUTO", "MANUAL"}
    assert TRADE_TYPES == {"NORMAL", "VUR_KAC"}
    assert LEVEL_SOURCES == {"SYSTEM", "USER_OVERRIDDEN"}

    assert normalize_control_mode(" manual ") == "MANUAL"
    assert normalize_control_mode("VUR_KAC") is None

    assert normalize_trade_type(" vur_kac ") == "VUR_KAC"
    assert normalize_trade_type("MANUAL_PANEL") is None

    assert normalize_level_source("system") == "SYSTEM"
    assert normalize_level_source("manual") is None


def test_legacy_trade_policy_maps_without_mixing_axes():
    assert legacy_trade_contract("NORMAL") == {
        "control_mode": "AUTO",
        "trade_type": "NORMAL",
    }
    assert legacy_trade_contract("VUR_KAC") == {
        "control_mode": "AUTO",
        "trade_type": "VUR_KAC",
    }
    assert legacy_trade_contract("MANUAL_PANEL") == {
        "control_mode": "MANUAL",
        "trade_type": "NORMAL",
    }
    assert legacy_trade_contract("UNKNOWN") is None


def test_schema_adds_canonical_trade_contract_columns(tmp_path):
    db = sqlite3.connect(tmp_path / "paper.db")
    result = ensure_paper_schema(db)

    columns = {
        row[1]
        for row in db.execute(
            "PRAGMA table_info(paper_trades)"
        )
    }

    assert {
        "trade_policy",
        "control_mode",
        "trade_type",
        "level_source",
    } <= columns
    assert result["schema_version"] >= 5

    db.close()


def test_schema_backfills_only_unambiguous_legacy_semantics(tmp_path):
    db = sqlite3.connect(tmp_path / "paper.db")
    ensure_paper_schema(db)

    rows = [
        ("0xnormal", "CLOSED", "NORMAL"),
        ("0xvk", "CLOSED", "VUR_KAC"),
        ("0xmanual", "CLOSED", "MANUAL_PANEL"),
        ("0xunknown", "CLOSED", "UNKNOWN"),
        ("0xblankclosed", "CLOSED", None),
        ("0xblankopen", "OPEN", None),
    ]

    db.executemany(
        """
        INSERT INTO paper_trades(
            token,
            status,
            trade_policy
        ) VALUES(?,?,?)
        """,
        rows,
    )
    db.commit()

    ensure_paper_schema(db)

    actual = {
        row[0]: row[1:]
        for row in db.execute(
            """
            SELECT
                token,
                trade_policy,
                control_mode,
                trade_type,
                level_source
            FROM paper_trades
            ORDER BY id
            """
        )
    }

    assert actual["0xnormal"] == (
        "NORMAL",
        "AUTO",
        "NORMAL",
        None,
    )
    assert actual["0xvk"] == (
        "VUR_KAC",
        "AUTO",
        "VUR_KAC",
        None,
    )
    assert actual["0xmanual"] == (
        "MANUAL_PANEL",
        "MANUAL",
        "NORMAL",
        None,
    )
    assert actual["0xunknown"] == (
        "UNKNOWN",
        None,
        None,
        None,
    )
    assert actual["0xblankclosed"] == (
        None,
        None,
        None,
        None,
    )
    assert actual["0xblankopen"] == (
        "VUR_KAC",
        "AUTO",
        "VUR_KAC",
        None,
    )

    db.close()


def test_existing_canonical_values_are_not_overwritten(tmp_path):
    db = sqlite3.connect(tmp_path / "paper.db")
    ensure_paper_schema(db)

    db.execute(
        """
        INSERT INTO paper_trades(
            token,
            status,
            trade_policy,
            control_mode,
            trade_type,
            level_source
        ) VALUES(?,?,?,?,?,?)
        """,
        (
            "0xcanonical",
            "CLOSED",
            "VUR_KAC",
            "MANUAL",
            "NORMAL",
            "USER_OVERRIDDEN",
        ),
    )
    db.commit()

    ensure_paper_schema(db)

    row = db.execute(
        """
        SELECT
            control_mode,
            trade_type,
            level_source
        FROM paper_trades
        WHERE token='0xcanonical'
        """
    ).fetchone()

    assert row == (
        "MANUAL",
        "NORMAL",
        "USER_OVERRIDDEN",
    )

    db.close()
