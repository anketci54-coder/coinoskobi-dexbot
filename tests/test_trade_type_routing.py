import sqlite3

import pytest

from app.paper.database import PaperDatabase
from app.paper.schema import ensure_paper_schema
from app.paper.trade_routing import (
    canonicalize_trade_axes,
    lifecycle_trade_type,
)


def test_legacy_auto_vur_kac_dual_writes_canonical_axes():
    row = canonicalize_trade_axes({
        "trade_policy": "VUR_KAC",
    })

    assert row["control_mode"] == "AUTO"
    assert row["trade_type"] == "VUR_KAC"


def test_legacy_manual_panel_becomes_manual_normal():
    row = canonicalize_trade_axes({
        "trade_policy": "MANUAL_PANEL",
    })

    assert row["control_mode"] == "MANUAL"
    assert row["trade_type"] == "NORMAL"


def test_explicit_canonical_axes_are_not_overwritten():
    row = canonicalize_trade_axes({
        "trade_policy": "VUR_KAC",
        "control_mode": "MANUAL",
        "trade_type": "NORMAL",
    })

    assert row["control_mode"] == "MANUAL"
    assert row["trade_type"] == "NORMAL"


def test_invalid_explicit_axes_fail_closed():
    with pytest.raises(ValueError, match="invalid control_mode"):
        canonicalize_trade_axes({
            "control_mode": "PAPER",
        })

    with pytest.raises(ValueError, match="invalid trade_type"):
        canonicalize_trade_axes({
            "trade_type": "MANUAL_PANEL",
        })


def test_lifecycle_uses_trade_type_before_legacy_policy():
    assert lifecycle_trade_type({
        "trade_type": "NORMAL",
        "trade_policy": "VUR_KAC",
    }) == "NORMAL"

    assert lifecycle_trade_type({
        "trade_type": "VUR_KAC",
        "trade_policy": "NORMAL",
    }) == "VUR_KAC"


def test_lifecycle_falls_back_to_legacy_only_when_trade_type_missing():
    assert lifecycle_trade_type({
        "trade_policy": "VUR_KAC",
    }) == "VUR_KAC"

    assert lifecycle_trade_type({
        "trade_policy": "MANUAL_PANEL",
    }) == "NORMAL"

    assert lifecycle_trade_type({
        "trade_policy": "UNKNOWN",
    }) is None


def test_invalid_explicit_trade_type_never_falls_back_to_legacy():
    assert lifecycle_trade_type({
        "trade_type": "BROKEN",
        "trade_policy": "VUR_KAC",
    }) is None


def test_database_insert_dual_writes_canonical_axes():
    database = object.__new__(PaperDatabase)
    database.conn = sqlite3.connect(":memory:")
    ensure_paper_schema(database.conn)

    database._insert_unlocked({
        "token": "0xmanual",
        "status": "CLOSED",
        "trade_policy": "MANUAL_PANEL",
    })

    row = database.conn.execute(
        """
        SELECT trade_policy, control_mode, trade_type
        FROM paper_trades
        WHERE token='0xmanual'
        """
    ).fetchone()

    assert row == (
        "MANUAL_PANEL",
        "MANUAL",
        "NORMAL",
    )


def test_database_insert_rejects_invalid_explicit_trade_type():
    database = object.__new__(PaperDatabase)
    database.conn = sqlite3.connect(":memory:")
    ensure_paper_schema(database.conn)

    with pytest.raises(ValueError, match="invalid trade_type"):
        database._insert_unlocked({
            "token": "0xbad",
            "status": "CLOSED",
            "trade_type": "MANUAL_PANEL",
        })
