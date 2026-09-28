import json
import sqlite3

from app.api import panel
from app.paper.schema import ensure_paper_schema


def _cache_db(path, *, pool, liquidity):
    db = sqlite3.connect(path)
    db.execute(
        """
        CREATE TABLE gecko_pool_cache (
            pool TEXT,
            token TEXT,
            quote_token TEXT,
            name TEXT,
            dex TEXT,
            liquidity REAL,
            volume24 REAL,
            buys24 INTEGER,
            fdv REAL,
            price_usd REAL,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    db.execute(
        """
        INSERT INTO gecko_pool_cache
        VALUES (?, '', '', '', '', ?, 0, 0, 0, 1, '', '')
        """,
        (pool, liquidity),
    )
    db.commit()
    db.close()


def test_paper_rows_can_return_all_active_rows(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"
    db = sqlite3.connect(db_path)
    ensure_paper_schema(db)
    db.execute(
        """
        INSERT INTO paper_runs (
            run_key, started_at, starting_capital_usdt,
            start_trade_id, start_realization_id,
            start_candidate_id, status, metadata_json
        ) VALUES ('RUN', 1, 10000, 0, 0, 0, 'ACTIVE', '{}')
        """
    )
    for _ in range(101):
        db.execute(
            """
            INSERT INTO paper_trades (
                status, paper_account_version, net_pnl_usdt
            ) VALUES ('CLOSED', 'PAPER_10K_V2', 0)
            """
        )
    for _ in range(2):
        db.execute(
            """
            INSERT INTO paper_trades (
                status, paper_account_version, entry_amount_usdt
            ) VALUES ('OPEN', 'PAPER_10K_V2', 1)
            """
        )
    db.commit()
    db.close()

    monkeypatch.setattr(panel, "PAPER_DB", db_path)

    assert len(panel.paper_rows(active_only=True)) == 100
    rows = panel.paper_rows(limit=None, active_only=True)
    assert len(rows) == 103
    assert sum(r["status"] == "OPEN" for r in rows) == 2


def test_dashboard_guard_marks_catastrophic_open_unverified(
    tmp_path,
    monkeypatch,
):
    paper_db = tmp_path / "paper.db"
    cache_db = tmp_path / "cache.db"
    pool = "0x" + "22" * 20

    db = sqlite3.connect(paper_db)
    ensure_paper_schema(db)
    db.execute(
        """
        INSERT INTO paper_trades (
            status, paper_account_version, pool,
            mathematical_plan_json, entry_amount_usdt,
            net_pnl_usdt
        ) VALUES ('OPEN', 'PAPER_10K_V2', ?, ?, 10, 9999)
        """,
        (
            pool,
            json.dumps({
                "capital": {
                    "observed_min_quote_reserve_usd": 100000.0,
                }
            }),
        ),
    )
    db.commit()
    db.close()

    _cache_db(
        cache_db,
        pool=pool,
        liquidity=0.0002,
    )
    monkeypatch.setattr(panel, "PAPER_DB", paper_db)
    monkeypatch.setattr(panel, "CACHE_DB", cache_db)

    rows = panel.paper_rows(limit=None)
    states = panel._dashboard_open_valuation_states(rows)

    state = states[rows[0]["id"]]
    assert state["state"] == "UNVERIFIED"
    assert (
        state["reason"]
        == "CATASTROPHIC_RESERVE_COLLAPSE"
    )
