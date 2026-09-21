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
    assert row["price_updated_at"]


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
    stale_price = "2026-01-01 00:00:01"

    cache.db.execute(
        """
        UPDATE gecko_pool_cache
        SET updated_at=?, price_updated_at=?
        WHERE lower(pool)=lower(?)
        """,
        (original, stale_price, "0xpool"),
    )
    cache.db.commit()

    assert cache.update_pool_price(
        "0xpool",
        0.00013,
    ) == 1

    row = cache.all()[0]

    assert row["price_usd"] == 0.00013
    assert row["updated_at"] == original
    assert row["price_updated_at"] != stale_price

    first_price_refresh = row[
        "price_updated_at"
    ]

    assert cache.upsert_tracked_price(
        "0xpool",
        "0xtoken",
        0.00014,
    ) is True

    row = cache.all()[0]

    assert row["price_usd"] == 0.00014
    assert row["updated_at"] == original
    assert row["price_updated_at"] >= (
        first_price_refresh
    )


def test_record_market_observation_preserves_provider_snapshot(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    assert cache.record_market_observation({
        "schema_version": (
            "DEXSCREENER_SNAPSHOT_V1"
        ),
        "chain": "bsc",
        "source": "dexscreener",
        "dex": "pancakeswap_v2",
        "pool": "0xpool",
        "base_token": "0xtoken",
        "quote_token": "0xquote",
        "price_usd": 0.000123,
        "liquidity_usd": 45678.0,
        "volume_h24_usd": 9876.0,
        "buys_h24": 55,
        "sells_h24": 21,
        "fdv_usd": 123456.0,
        "market_cap_usd": 120000.0,
        "pair_created_at_ms": 1234567890,
        "observed_at": (
            "2026-09-21T11:04:00+00:00"
        ),
    }) is True

    row = cache.db.execute(
        """
        SELECT
            schema_version,
            chain,
            source,
            dex,
            pool,
            token,
            quote_token,
            price_usd,
            liquidity_usd,
            volume_24h,
            buys_24h,
            sells_24h,
            fdv_usd,
            market_cap_usd,
            observed_at
        FROM market_observation_history
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    assert row is not None
    assert row[0] == (
        "DEXSCREENER_SNAPSHOT_V1"
    )
    assert row[1] == "bsc"
    assert row[2] == "dexscreener"
    assert row[3] == "pancakeswap_v2"
    assert row[4] == "0xpool"
    assert row[5] == "0xtoken"
    assert row[6] == "0xquote"
    assert row[7] == 0.000123
    assert row[8] == 45678.0
    assert row[9] == 9876.0
    assert row[10] == 55
    assert row[11] == 21
    assert row[12] == 123456.0
    assert row[13] == 120000.0
    assert row[14] == (
        "2026-09-21T11:04:00+00:00"
    )
