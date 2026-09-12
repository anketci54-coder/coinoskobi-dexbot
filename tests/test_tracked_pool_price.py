import app.cache.gecko_cache as module


def test_tracked_price_recreates_missing_cache_row(tmp_path, monkeypatch):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    assert cache.update_pool_price(
        "0xpool",
        1.25,
    ) == 0

    assert cache.upsert_tracked_price(
        "0xpool",
        "0xtoken",
        1.25,
    ) is True

    assert cache.pool_for_token(
        "0xtoken"
    ) == "0xpool"

    row = cache.all()[0]

    assert row["price_usd"] == 1.25
    assert row["token"] == "bsc_0xtoken"


def test_price_only_refresh_preserves_market_quality_timestamp(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    cache.replace({
        "pool": "0xpool",
        "base_token": "bsc_0xtoken",
        "quote_token": "bsc_0xquote",
        "name": "TOKEN / WBNB",
        "dex": "pancakeswap_v2",
        "liquidity": 35000.0,
        "volume_24h": 12000.0,
        "buys_24h": 40,
        "fdv": 120000.0,
        "price_usd": 0.00012,
        "created_at": None,
    })

    original = "2026-01-01 00:00:00"

    cache.db.execute(
        """
        UPDATE gecko_pool_cache
        SET updated_at=?
        WHERE lower(pool)=lower(?)
        """,
        (original, "0xpool"),
    )
    cache.db.commit()

    assert cache.update_pool_price(
        "0xpool",
        0.00013,
    ) == 1

    row = cache.all()[0]

    assert row["price_usd"] == 0.00013
    assert row["updated_at"] == original

    assert cache.upsert_tracked_price(
        "0xpool",
        "0xtoken",
        0.00014,
    ) is True

    row = cache.all()[0]

    assert row["price_usd"] == 0.00014
    assert row["updated_at"] == original
