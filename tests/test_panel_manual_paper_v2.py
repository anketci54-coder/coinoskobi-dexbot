import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.panel_manual_paper_v2 import _buy, _preview_buy, _preview_sell, _sell
from app.scanner.gecko_scanner import GeckoScanner
from app.paper.schema import ensure_paper_schema
from app.risk.paper_position_sizing import paper_available_capital_usdt
from app.config.contracts import USDT
from app.risk.price_integrity import PriceIntegrityGate
from tests.price_integrity_support import V2RPC
TOKEN = "bsc_0x1111111111111111111111111111111111111111"
POOL = "0x2222222222222222222222222222222222222222"


def _verified_gate(price):
    return PriceIntegrityGate(
        V2RPC(
            price=price,
            token=TOKEN.removeprefix("bsc_"),
            pool=POOL,
        )
    )



def _paper_db(path):
    db = sqlite3.connect(path)
    ensure_paper_schema(db)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS
        candidate_decision_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            pool TEXT NOT NULL,
            observed_at REAL NOT NULL,
            context_json TEXT NOT NULL
        )
        """
    )

    plan = {
        "contract": (
            "mathematical_trade_plan"
        ),
        "hard_block": False,
        "sellability_status": (
            "SELLABILITY_OK"
        ),
        "entry": {
            "price": 2.0,
        },
        "capital": {
            "entry_amount_usdt": 0.0,
        },
        "position": {
            "token_amount": 0.0,
            "initial_risk_usdt": 0.0,
        },
        "sl": {
            "initial_price": (
                2.0
                * __import__(
                    "math"
                ).exp(-0.10)
            ),
            "risk_log_distance": 0.10,
        },
        "tp1": {
            "activation_price": None,
        },
        "tp2": {
            "activation_price": None,
        },
        "runner": {
            "rule": (
                "FOLLOW_MONOTONIC_EMPIRICAL_TREND_FLOOR_UNTIL_BREAK"
            ),
        },
        "statistics": {
            "risk_log_distance": 0.10,
            "prices": [
                1.8,
                1.9,
                2.0,
            ],
        },
        "cost_model": {
            "buy_gas_usd": 0.0,
            "sell_gas_usd": 0.0,
            "buy_retention_known": 1.0,
            "sell_retention_known": 1.0,
            "cost_complete": False,
        },
    }

    context = {
        "hard_block": False,
        "sellability": (
            "SELLABILITY_OK"
        ),
        "mathematical_plan": plan,
    }

    db.execute(
        """
        INSERT INTO
        candidate_decision_history(
            token,
            pool,
            observed_at,
            context_json
        )
        VALUES(?,?,?,?)
        """,
        (
            TOKEN,
            POOL,
            time.time(),
            json.dumps(context),
        ),
    )

    db.commit()
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
            quote_token TEXT,
            price_usd REAL,
            updated_at TEXT
        )
        """
    )
    observed = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    db.execute(
        "INSERT INTO gecko_pool_cache VALUES(?,?,?,?,?,?,?)",
        (POOL, TOKEN, "TEST/USDT", "pancakeswap_v2", USDT, price, observed.isoformat()),
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


def test_manual_paper_buy_sell_round_trip_and_balance_conservation(tmp_path, monkeypatch):
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
    assert row["control_mode"] == "MANUAL"
    assert row["trade_type"] == "NORMAL"
    assert row["level_source"] == "SYSTEM"
    assert row["sl_price"] > 0
    assert row["sl_price"] < row["entry_price"]
    assert row["tp_price"] > row["entry_price"]
    assert row["mathematical_plan_json"]
    assert row["math_state_json"]
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


def _cache_db_with_universe(
    path,
    *,
    gecko_price=2.0,
    gecko_age_seconds=600,
    universe_price=2.5,
    universe_age_seconds=0,
):
    db = sqlite3.connect(path)

    db.execute(
        """
        CREATE TABLE gecko_pool_cache(
            pool TEXT PRIMARY KEY,
            token TEXT,
            name TEXT,
            dex TEXT,
            quote_token TEXT,
            price_usd REAL,
            updated_at TEXT
        )
        """
    )

    gecko_observed = (
        datetime.now(timezone.utc)
        - timedelta(
            seconds=gecko_age_seconds
        )
    )

    db.execute(
        """
        INSERT INTO gecko_pool_cache
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            POOL,
            TOKEN,
            "TEST/USDT",
            "pancakeswap_v2",
            USDT,
            gecko_price,
            gecko_observed.isoformat(),
        ),
    )

    db.execute(
        """
        CREATE TABLE universe_pool_registry(
            pool TEXT,
            token0 TEXT,
            dex TEXT,
            quote_token TEXT,
            latest_price_usd REAL,
            latest_snapshot_at TEXT
        )
        """
    )

    universe_observed = (
        datetime.now(timezone.utc)
        - timedelta(
            seconds=universe_age_seconds
        )
    )

    db.execute(
        """
        INSERT INTO universe_pool_registry(
            pool,
            token0,
            dex,
            quote_token,
            latest_price_usd,
            latest_snapshot_at
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            POOL,
            TOKEN,
            "pancakeswap_v2",
            USDT,
            universe_price,
            universe_observed.isoformat(),
        ),
    )

    db.commit()
    db.close()


def test_manual_buy_uses_fresh_universe_price_when_gecko_is_stale(
    tmp_path,
monkeypatch,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)

    _cache_db_with_universe(
        cache,
        gecko_price=2.0,
        gecko_age_seconds=600,
        universe_price=2.5,
        universe_age_seconds=0,
    )

    bought = _buy(
        paper_db=paper,
        cache_db=cache,
        payload={
            "token": TOKEN,
            "pool": POOL,
            "symbol": "TEST",
            "amount_usdt": 100.0,
        },
    )

    assert bought["reference_price"] == 2.5

    assert (
        bought["reference_price_source"]
        == "UNIVERSE_POOL_REGISTRY"
    )

    assert bought["token_amount"] == pytest.approx(
        40.0
    )


def test_manual_buy_prefers_newest_valid_quote_source(
    tmp_path,
monkeypatch,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)

    _cache_db_with_universe(
        cache,
        gecko_price=3.0,
        gecko_age_seconds=0,
        universe_price=2.5,
        universe_age_seconds=30,
    )

    bought = _buy(
        paper_db=paper,
        cache_db=cache,
        payload={
            "token": TOKEN,
            "pool": POOL,
            "symbol": "TEST",
            "amount_usdt": 90.0,
        },
    )

    assert bought["reference_price"] == 3.0

    assert (
        bought["reference_price_source"]
        == "GECKO_POOL_CACHE"
    )

    assert bought["token_amount"] == pytest.approx(
        30.0
    )


def test_manual_buy_uses_ondemand_pool_quote_when_all_cache_is_stale(
    tmp_path,
    monkeypatch,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)

    _cache_db_with_universe(
        cache,
        gecko_price=2.0,
        gecko_age_seconds=600,
        universe_price=2.5,
        universe_age_seconds=600,
    )

    calls = []

    def pool_snapshots(
        self,
        pools,
        max_pools=30,
        *,
        persist_followups=True,
    ):
        calls.append(
            {
                "pools": list(pools),
                "max_pools": max_pools,
                "persist_followups": (
                    persist_followups
                ),
            }
        )

        return [
            {
                "pool": POOL,
                "base_token": TOKEN,
                "name": "TEST/USDT",
                "dex": "pancakeswap_v2",
                "quote_token": USDT,
                "price_usd": 4.0,
            }
        ]

    monkeypatch.setattr(
        GeckoScanner,
        "pool_snapshots",
        pool_snapshots,
    )

    bought = _buy(
        paper_db=paper,
        cache_db=cache,
        payload={
            "token": TOKEN,
            "pool": POOL,
            "symbol": "TEST",
            "amount_usdt": 100.0,
        },
    )

    assert bought["reference_price"] == 4.0

    assert (
        bought["reference_price_source"]
        == "GECKOTERMINAL_ON_DEMAND"
    )

    assert bought["token_amount"] == pytest.approx(
        25.0
    )

    assert len(calls) == 1
    assert calls[0]["pools"] == [POOL.lower()]
    assert calls[0]["max_pools"] == 1
    assert calls[0]["persist_followups"] is False


def test_fresh_cache_does_not_make_ondemand_request(
    tmp_path,
    monkeypatch,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)
    _cache_db(
        cache,
        price=2.0,
        age_seconds=0,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "ON_DEMAND_MUST_NOT_RUN"
        )

    monkeypatch.setattr(
        GeckoScanner,
        "pool_snapshots",
        forbidden,
    )

    bought = _buy(
        paper_db=paper,
        cache_db=cache,
        payload={
            "token": TOKEN,
            "pool": POOL,
            "symbol": "TEST",
            "amount_usdt": 10.0,
        },
    )

    assert bought["reference_price"] == 2.0

    assert (
        bought["reference_price_source"]
        == "GECKO_POOL_CACHE"
    )


def test_manual_sell_preview_is_read_only_and_uses_fresh_price(
    tmp_path,
monkeypatch,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)
    _cache_db(
        cache,
        price=2.0,
    )

    bought = _buy(
        paper_db=paper,
        cache_db=cache,
        payload={
            "token": TOKEN,
            "pool": POOL,
            "symbol": "TEST",
            "amount_usdt": 100.0,
        },
    )

    _set_price(
        cache,
        2.2,
    )

    preview = _preview_sell(
        paper_db=paper,
        cache_db=cache,
        payload={
            "position_id": (
                bought["position_id"]
            ),
            "pool": POOL,
            "token": TOKEN,
        },
    )

    assert preview["preview_only"] is True
    assert preview["paper_only"] is True
    assert preview["live_execution"] is False
    assert preview["decision_authority"] is False

    assert preview["reference_price"] == pytest.approx(
        2.2
    )

    assert preview["proceeds_usdt"] == pytest.approx(
        110.0
    )

    assert preview["net_pnl_usdt"] == pytest.approx(
        10.0
    )

    assert preview["roi_pct"] == pytest.approx(
        10.0
    )

    assert preview["break_even_price"] == pytest.approx(
        2.0
    )

    db = sqlite3.connect(paper)

    status = db.execute(
        """
        SELECT status
        FROM paper_trades
        WHERE id=?
        """,
        (
            bought["position_id"],
        ),
    ).fetchone()[0]

    db.close()

    assert status == "OPEN"


def test_manual_preview_route_exists_without_trade_confirmation():
    source = __import__(
        "pathlib"
    ).Path(
        "app/api/panel_manual_paper_v2.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '@app.post("/api/manual-paper/preview-v2")'
        in source
    )

    assert (
        '"preview_only": True'
        in source
    )


def test_manual_buy_preview_returns_canonical_normal_plan(
    tmp_path,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)
    _cache_db(
        cache,
        price=2.0,
    )

    preview = (
        _preview_buy(
            paper_db=paper,
            cache_db=cache,
            payload={
                "side": "BUY",
                "token": TOKEN,
                "pool": POOL,
                "symbol": "TEST",
                "amount_usdt": 100.0,
            },
        )
    )

    assert preview[
        "preview_only"
    ] is True

    assert preview[
        "control_mode"
    ] == "MANUAL"

    assert preview[
        "trade_type"
    ] == "NORMAL"

    assert preview[
        "level_source"
    ] == "SYSTEM"

    assert preview[
        "sl_price"
    ] < preview[
        "reference_price"
    ]

    assert preview[
        "tp1_price"
    ] > preview[
        "reference_price"
    ]

    assert preview[
        "tp2_mode"
    ] == "DYNAMIC_PRINCIPAL_RECOVERY"

    assert preview[
        "tp3_mode"
    ] == "TREND_RUNNER"


def test_manual_buy_level_override_provenance(
    tmp_path,
monkeypatch,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)
    _cache_db(
        cache,
        price=2.0,
    )

    bought = _buy(
        paper_db=paper,
        cache_db=cache,
        payload={
            "token": TOKEN,
            "pool": POOL,
            "symbol": "TEST",
            "amount_usdt": 100.0,
            "sl_price": 1.70,
            "tp1_price": 2.50,
        },
    )

    assert bought[
        "level_source"
    ] == "USER_OVERRIDDEN"

    db = sqlite3.connect(
        paper
    )
    db.row_factory = sqlite3.Row

    row = dict(
        db.execute(
            """
            SELECT *
            FROM paper_trades
            WHERE id=?
            """,
            (
                bought[
                    "position_id"
                ],
            ),
        ).fetchone()
    )

    assert row[
        "control_mode"
    ] == "MANUAL"

    assert row[
        "trade_type"
    ] == "NORMAL"

    assert row[
        "level_source"
    ] == "USER_OVERRIDDEN"

    assert row[
        "sl_price"
    ] == pytest.approx(
        1.70
    )

    assert row[
        "tp_price"
    ] == pytest.approx(
        2.50
    )

    context = json.loads(
        row[
            "opening_context_json"
        ]
    )

    assert (
        context[
            "level_sources"
        ]["sl"]
        == "USER_OVERRIDDEN"
    )

    assert (
        context[
            "level_sources"
        ]["tp1"]
        == "USER_OVERRIDDEN"
    )

    db.close()


def test_manual_buy_hard_block_fails_closed(
    tmp_path,
):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    _paper_db(paper)
    _cache_db(
        cache,
        price=2.0,
    )

    db = sqlite3.connect(
        paper
    )

    context = {
        "hard_block": True,
        "sellability": (
            "SELLABILITY_OK"
        ),
        "mathematical_plan": {
            "hard_block": True,
        },
    }

    db.execute(
        """
        INSERT INTO
        candidate_decision_history(
            token,
            pool,
            observed_at,
            context_json
        )
        VALUES(?,?,?,?)
        """,
        (
            TOKEN,
            POOL,
            time.time() + 1,
            json.dumps(context),
        ),
    )

    db.commit()
    db.close()

    with pytest.raises(
        HTTPException
    ) as exc:
        _buy(
            paper_db=paper,
            cache_db=cache,
            payload={
                "token": TOKEN,
                "pool": POOL,
                "amount_usdt": 100.0,
            },
        )

    assert (
        exc.value.status_code
        == 409
    )

    assert (
        "hard block"
        in str(
            exc.value.detail
        ).lower()
    )
