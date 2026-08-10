from datetime import datetime, timedelta, timezone

import app.cache.gecko_cache as cache_module
import app.filter.cache_filter as filter_module
from app.cache.gecko_cache import GeckoCache
from app.filter.cache_filter import CacheFilter


def iso_utc(delta=None):
    now = datetime.now(timezone.utc)

    if delta is not None:
        now += delta

    return now.isoformat()


def good_row(**overrides):
    row = {
        "pool": "0xpool",
        "token": "bsc_0xtoken",
        "name": "Example",
        "dex": "pancakeswap_v2",
        "liquidity": 10_000,
        "volume_24h": 5_000,
        "buys_24h": 20,
        "fdv": 100_000,
        "price_usd": 0.001,
        "created_at": iso_utc(timedelta(hours=-1)),
        "updated_at": iso_utc(timedelta(minutes=-1)),
    }
    row.update(overrides)
    return row


def test_gecko_cache_all_returns_canonical_filter_fields(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "cache.db"

    monkeypatch.setattr(cache_module, "DB", db_path)

    cache = GeckoCache()

    cache.replace({
        "pool": "0xpool",
        "base_token": "bsc_0xtoken",
        "name": "Example",
        "dex": "pancakeswap_v2",
        "liquidity": 10_000,
        "volume_24h": 5_000,
        "buys_24h": 20,
        "fdv": 100_000,
        "price_usd": 0.001,
        "created_at": iso_utc(timedelta(hours=-1)),
    })

    rows = cache.all()

    assert len(rows) == 1
    assert rows[0]["volume_24h"] == 5_000
    assert rows[0]["buys_24h"] == 20
    assert rows[0]["updated_at"]


def test_cache_filter_accepts_valid_fresh_row():
    result = CacheFilter().filter([good_row()])

    assert len(result) == 1
    assert result[0]["volume_24h"] == 5_000
    assert result[0]["buys_24h"] == 20


def test_cache_filter_rejects_stale_cache_row(monkeypatch):
    stale = good_row(
        updated_at=iso_utc(
            timedelta(
                minutes=-(filter_module.CACHE_MAX_AGE_MINUTES + 5)
            )
        )
    )

    assert CacheFilter().filter([stale]) == []


def test_cache_filter_rejects_old_pool():
    old = good_row(
        created_at=iso_utc(
            timedelta(
                hours=-(filter_module.MAX_POOL_AGE_HOURS + 1)
            )
        )
    )

    assert CacheFilter().filter([old]) == []




def test_cache_filter_returns_all_valid_candidates():
    rows = []

    for index in range(10):
        rows.append(
            good_row(
                pool=f"pool-{index}",
                liquidity=10_000 + index,
            )
        )

    result = CacheFilter().filter(rows)

    assert len(result) == 10
    assert result[0]["liquidity"] > result[-1]["liquidity"]


def test_bad_cache_row_does_not_block_valid_candidate():
    malformed = good_row(
        pool="bad",
        liquidity="not-a-number",
    )

    valid = good_row(
        pool="good",
    )

    result = CacheFilter().filter([
        malformed,
        valid,
    ])

    assert len(result) == 1
    assert result[0]["pool"] == "good"
