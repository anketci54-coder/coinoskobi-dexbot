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
