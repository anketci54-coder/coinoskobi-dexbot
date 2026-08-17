import sqlite3

import pytest

import app.api.panel as panel_module
from app.paper.schema import ensure_paper_schema


@pytest.fixture
def panel_db(tmp_path, monkeypatch):
    db_path = tmp_path / "panel_paper10k.db"

    conn = sqlite3.connect(db_path)
    ensure_paper_schema(conn)

    rows = [
        {
            "token": "0xlegacywin",
            "symbol": "LEGACY_WIN",
            "status": "CLOSED",
            "entry_price": 1.0,
            "current_price": 2.0,
            "highest_price": 2.0,
            "lowest_price": 1.0,
            "token_amount": 1.0,
            "net_pnl": 999.0,
            "roi": 1.0,
            "close_reason": "TAKE_PROFIT",
            "paper_account_version": None,
            "net_pnl_usdt": None,
        },
        {
            "token": "0xpaperwin",
            "symbol": "PAPER_WIN",
            "status": "CLOSED",
            "entry_price": 1.0,
            "current_price": 1.2,
            "highest_price": 1.2,
            "lowest_price": 1.0,
            "token_amount": 100.0,
            "net_pnl": 20.0,
            "roi": 0.20,
            "close_reason": "TAKE_PROFIT",
            "paper_account_version": "PAPER_10K_V1",
            "net_pnl_usdt": 20.0,
        },
        {
            "token": "0xpaperloss",
            "symbol": "PAPER_LOSS",
            "status": "CLOSED",
            "entry_price": 1.0,
            "current_price": 0.9,
            "highest_price": 1.0,
            "lowest_price": 0.9,
            "token_amount": 100.0,
            "net_pnl": -10.0,
            "roi": -0.10,
            "close_reason": "STOP_LOSS",
            "paper_account_version": "PAPER_10K_V1",
            "net_pnl_usdt": -10.0,
        },
        {
            "token": "0xpaperopen",
            "symbol": "PAPER_OPEN",
            "status": "OPEN",
            "entry_price": 1.0,
            "current_price": 1.0,
            "highest_price": 1.0,
            "lowest_price": 1.0,
            "token_amount": 100.0,
            "net_pnl": 0.0,
            "roi": 0.0,
            "close_reason": None,
            "paper_account_version": "PAPER_10K_V1",
            "net_pnl_usdt": 0.0,
        },
    ]

    for row in rows:
        columns = ",".join(row)
        placeholders = ",".join("?" for _ in row)

        conn.execute(
            f"""
            INSERT INTO paper_trades ({columns})
            VALUES ({placeholders})
            """,
            tuple(row.values()),
        )

    conn.commit()
    conn.close()

    monkeypatch.setattr(
        panel_module,
        "PAPER_DB",
        db_path,
    )

    return db_path


def test_status_counts_only_paper_10k_generation(panel_db):
    result = panel_module.status()

    assert result["total"] == 3
    assert result["new_generation"] == 3
    assert result["open_positions"] == 1
    assert result["closed_positions"] == 2


def test_performance_uses_paper_10k_usdt_accounting(panel_db):
    result = panel_module.performance()

    assert result["closed"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["win_rate_pct"] == pytest.approx(50.0)
    assert result["avg_roi_pct"] == pytest.approx(5.0)
    assert result["net_total"] == pytest.approx(10.0)


def test_exits_use_only_paper_10k_usdt_accounting(panel_db):
    result = panel_module.exits()

    by_reason = {
        row["close_reason"]: row
        for row in result
    }

    assert set(by_reason) == {
        "TAKE_PROFIT",
        "STOP_LOSS",
    }

    take_profit = by_reason["TAKE_PROFIT"]
    assert take_profit["trades"] == 1
    assert take_profit["avg_roi_pct"] == pytest.approx(20.0)
    assert take_profit["net_total"] == pytest.approx(20.0)

    stop_loss = by_reason["STOP_LOSS"]
    assert stop_loss["trades"] == 1
    assert stop_loss["avg_roi_pct"] == pytest.approx(-10.0)
    assert stop_loss["net_total"] == pytest.approx(-10.0)
