from datetime import datetime, timezone

import app.cache.gecko_cache as gecko_cache_module
from app.cache.gecko_cache import GeckoCache
from app.dex.native_ingestion import SYNC_TOPIC
from app.dex.open_position_hot_path import (
    HotPositionWSSBridge,
    process_hot_positions,
)


PAIR = "0x" + "11" * 20
TOKEN = "0x" + "01" * 20
QUOTE = "0x" + "ff" * 20


def _fresh_timestamp():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _position():
    return {
        "id": 1,
        "status": "OPEN",
        "trade_policy": "VUR_KAC",
        "token": TOKEN,
        "pool": PAIR,
        "dex": "pancakeswap_v2",
        "opening_context_json": "{}",
    }


def _row(
    *,
    price_updated_at,
    price=7.5,
    updated_at="2000-01-01 00:00:00",
):
    return {
        "pool": PAIR,
        "token": f"bsc_{TOKEN}",
        "quote_token": f"bsc_{QUOTE}",
        "dex": "pancakeswap_v2",
        "price_usd": price,
        "updated_at": updated_at,
        "price_updated_at": price_updated_at,
    }


def _word(value):
    return f"{value:064x}"


def _sync_event(reserve0, reserve1):
    return {
        "address": PAIR,
        "topics": [SYNC_TOPIC],
        "data": (
            "0x"
            + _word(reserve0)
            + _word(reserve1)
        ),
    }


class _DB:
    def open_positions(self):
        return [_position()]


class _Cache:
    def __init__(self, row):
        self.row = dict(row)
        self.update_calls = []

    def all(self):
        return [dict(self.row)]

    def pool_for_token(self, token):
        return PAIR

    def update_pool_price(self, pool, price):
        self.update_calls.append((pool, price))
        self.row["price_usd"] = float(price)
        self.row[
            "price_updated_at"
        ] = _fresh_timestamp()
        return 1


class _FallbackPrice:
    def get_price(self, token):
        return 99.0


class _Manager:
    def __init__(self):
        self.db = _DB()
        self.price = _FallbackPrice()
        self.hybrid_exit_evidence = None

    def process(self):
        return [self.price.get_price(TOKEN)]


class _Pipeline:
    def __init__(self, row):
        self.cache = _Cache(row)
        self.manager = _Manager()
        self.pair_membership_verifier = (
            lambda *_: {"state": "VERIFIED"}
        )

    def _hybrid_exit_runtime_evidence(
        self,
        position,
    ):
        return {"state": "READY"}


def test_stale_exact_open_pool_price_cannot_fall_back_to_token_cache():
    pipeline = _Pipeline(
        _row(
            price_updated_at=(
                "2000-01-01 00:00:00"
            )
        )
    )

    result = process_hot_positions(pipeline)

    assert result == [None]


def test_fresh_exact_open_pool_price_is_used():
    pipeline = _Pipeline(
        _row(
            price_updated_at=(
                _fresh_timestamp()
            )
        )
    )

    result = process_hot_positions(pipeline)

    assert result == [7.5]


def test_stale_cache_price_cannot_anchor_wss_ratio():
    pipeline = _Pipeline(
        _row(
            price_updated_at=(
                "2000-01-01 00:00:00"
            )
        )
    )
    bridge = HotPositionWSSBridge()
    bridge.replace_targets(
        [
            {
                "pair": PAIR,
                "token": TOKEN,
                "quote_token": QUOTE,
            }
        ],
        open_pairs=[PAIR],
    )
    bridge.observe_event(
        _sync_event(100, 200)
    )

    result = bridge.drain_price_updates(
        pipeline
    )

    assert result["state"] == "NO_UPDATE"
    assert result["updated"] == 0
    assert result["anchored"] == 0
    assert result["failed"] == 1


def test_live_cache_price_updates_refresh_only_price_timestamp(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cache.db"
    monkeypatch.setattr(
        gecko_cache_module,
        "DB",
        db_path,
    )

    cache = GeckoCache()
    cache.replace({
        "pool": PAIR,
        "base_token": f"bsc_{TOKEN}",
        "quote_token": f"bsc_{QUOTE}",
        "name": "TOKEN / WBNB",
        "dex": "pancakeswap_v2",
        "liquidity": 35000.0,
        "volume_24h": 12000.0,
        "buys_24h": 40,
        "fdv": 120000.0,
        "price_usd": 7.0,
        "created_at": None,
    })

    market_timestamp = "2000-01-01 00:00:00"
    stale_price_timestamp = "2000-01-02 00:00:00"
    cache.db.execute(
        "UPDATE gecko_pool_cache "
        "SET updated_at=?, price_updated_at=? "
        "WHERE pool=?",
        (
            market_timestamp,
            stale_price_timestamp,
            PAIR,
        ),
    )
    cache.db.commit()

    cache.update_pool_price(
        PAIR,
        8.0,
    )
    row = cache.all()[0]
    assert row["updated_at"] == market_timestamp
    assert (
        row["price_updated_at"]
        != stale_price_timestamp
    )

    refreshed_price_timestamp = (
        row["price_updated_at"]
    )

    cache.upsert_tracked_price(
        PAIR,
        TOKEN,
        8.5,
    )
    row = cache.all()[0]
    assert row["updated_at"] == market_timestamp
    assert row["price_updated_at"] >= (
        refreshed_price_timestamp
    )


def test_full_market_replace_refreshes_both_timestamps(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cache.db"
    monkeypatch.setattr(
        gecko_cache_module,
        "DB",
        db_path,
    )

    cache = GeckoCache()
    cache.replace({
        "pool": PAIR,
        "base_token": f"bsc_{TOKEN}",
        "quote_token": f"bsc_{QUOTE}",
        "name": "TOKEN / WBNB",
        "dex": "pancakeswap_v2",
        "liquidity": 35000.0,
        "volume_24h": 12000.0,
        "buys_24h": 40,
        "fdv": 120000.0,
        "price_usd": 7.0,
        "created_at": None,
    })

    row = cache.all()[0]
    assert row["updated_at"]
    assert row["price_updated_at"]
