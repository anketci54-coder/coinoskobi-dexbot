import app.cache.gecko_cache as module


def row(pool, token):
    return {
        "pool": pool,
        "base_token": f"bsc_{token}",
        "quote_token": "bsc_0xquote",
        "name": "TOKEN/WBNB",
        "dex": "pancakeswap_v2",
        "liquidity": 10000,
        "volume_24h": 5000,
        "buys_24h": 20,
        "fdv": 50000,
        "price_usd": 1.0,
        "created_at": "2026-08-14T00:00:00Z",
    }


def test_prune_keeps_snapshot_and_open_position(tmp_path, monkeypatch):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()
    cache.replace(row("0xpool1", "0xtoken1"))
    cache.replace(row("0xpool2", "0xtoken2"))
    cache.replace(row("0xpool3", "0xtoken3"))

    removed = cache.prune_except(
        ["0xpool1"],
        preserve_tokens=["0xtoken2"],
    )

    pools = {
        item["pool"]
        for item in cache.all()
    }

    assert removed == 1
    assert pools == {"0xpool1", "0xpool2"}


def test_empty_snapshot_does_not_delete_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()
    cache.replace(row("0xpool1", "0xtoken1"))

    assert cache.prune_except([]) == 0
    assert len(cache.all()) == 1
