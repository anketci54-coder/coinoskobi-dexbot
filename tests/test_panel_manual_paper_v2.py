import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.panel_manual_paper_v2 import _buy, _sell
from app.paper.schema import ensure_paper_schema
from app.risk.paper_position_sizing import paper_available_capital_usdt


TOKEN = "bsc_0x1111111111111111111111111111111111111111"
POOL = "0x2222222222222222222222222222222222222222"


def _paper_db(path):
    db = sqlite3.connect(path)
    ensure_paper_schema(db)
    db.close()


def _cache_db(path, *, price=2.0, age_seconds=0):
    db = sqlite3.connect(path)
    db.execute(
        """
        CREATE TABLE gecko_pool_cache(
            pool TEXT PRIMARY KEY,
            token TEXT,
            name TEXT,
            dex TEXT,
            price_usd REAL,
            updated_at TEXT
        )
        """
    )
    observed = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    db.execute(
        "INSERT INTO gecko_pool_cache VALUES(?,?,?,?,?,?)",
        (POOL, TOKEN, "TEST/USDT", "pancakeswap", price, observed.isoformat()),
    )
    db.commit()
    db.close()


def _set_price(path, price):
    db = sqlite3.connect(path)
    db.execute(
        "UPDATE gecko_pool_cache SET price_usd=?, updated_at=? WHERE pool=?",
        (price, datetime.now(timezone.utc).isoformat(), POOL),
    )
    db.commit()
    db.close()


def test_manual_paper_buy_sell_round_trip_and_balance_conservation(tmp_path):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"
    _paper_db(paper)
    _cache_db(cache, price=2.0)

    bought = _buy(
        paper_db=paper,
        cache_db=cache,
        payload={"token": TOKEN, "pool": POOL, "symbol": "TEST", "amount_usdt": 100.0},
    )
    assert bought["paper_only"] is True
    assert bought["live_execution"] is False
    assert bought["wallet_authority"] is False
    assert bought["signing_authority"] is False
    assert bought["reference_price"] == 2.0
    assert bought["token_amount"] == 50.0
    assert bought["paper_balance_after"] == 9900.0

    db = sqlite3.connect(paper)
    db.row_factory = sqlite3.Row
    row = dict(db.execute("SELECT * FROM paper_trades WHERE id=?", (bought["position_id"],)).fetchone())
    assert row["status"] == "OPEN"
    assert row["trade_policy"] == "MANUAL_PANEL"
    assert row["initial_token_amount"] == 50.0
    assert row["remaining_cost_basis_usdt"] == 100.0
    assert paper_available_capital_usdt(db) == 9900.0
    db.close()

    _set_price(cache, 2.2)
    sold = _sell(
        paper_db=paper,
        cache_db=cache,
        payload={"position_id": bought["position_id"], "token": TOKEN, "pool": POOL},
    )
    assert sold["reference_price"] == 2.2
    assert sold["proceeds_usdt"] == pytest.approx(110.0)
    assert sold["net_pnl_usdt"] == pytest.approx(10.0)
    assert sold["roi_pct"] == pytest.approx(10.0)

    db = sqlite3.connect(paper)
    db.row_factory = sqlite3.Row
    row = dict(db.execute("SELECT * FROM paper_trades WHERE id=?", (bought["position_id"],)).fetchone())
    assert row["status"] == "CLOSED"
    assert row["close_reason"] == "MANUAL_PAPER_SELL"
    assert row["token_amount"] == 0.0
    assert row["remaining_cost_basis_usdt"] == 0.0
    assert row["net_pnl_usdt"] == pytest.approx(10.0)
    assert row["realized_proceeds_usdt"] == pytest.approx(110.0)
    assert paper_available_capital_usdt(db) == pytest.approx(10010.0)
    db.close()


def test_manual_paper_rejects_stale_quote_before_buy(tmp_path):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"
    _paper_db(paper)
    _cache_db(cache, price=2.0, age_seconds=600)

    with pytest.raises(HTTPException) as exc:
        _buy(
            paper_db=paper,
            cache_db=cache,
            payload={"token": TOKEN, "pool": POOL, "amount_usdt": 10.0},
        )
    assert exc.value.status_code == 409
    assert "bayat" in str(exc.value.detail).lower()

    db = sqlite3.connect(paper)
    assert db.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0] == 0
    db.close()


def test_manual_paper_rejects_unconfirmed_or_unsafe_partial_close_contract_by_design():
    source = __import__("pathlib").Path("app/api/panel_manual_paper_v2.py").read_text(encoding="utf-8")
    assert 'payload.get("confirmed") is not True' in source
    assert "Kısmi pozisyon maliyet modeli eksik" in source
    assert "MANUAL_QUOTE_MAX_AGE_SECONDS = 300.0" in source
    assert "live_execution" in source
    assert "wallet_authority" in source
    assert "signing_authority" in source
