from app.pipeline.engine import PipelineEngine


class DB:
    def open_positions(self):
        return [
            {"token": "0xtoken1"},
            {"token": "0xtoken2"},
        ]


class Cache:
    def __init__(self):
        self.updated = []

    def pool_for_token(self, token):
        return {
            "0xtoken1": "0xpool1",
            "0xtoken2": "0xpool2",
        }[token]

    def update_pool_price(self, pool, price):
        self.updated.append((pool, price))
        return 1


class Scanner:
    def pool_price(self, pool):
        return {
            "0xpool1": 1.25,
            "0xpool2": 2.50,
        }[pool]


def test_open_position_prices_refresh_before_manager():
    engine = PipelineEngine.__new__(PipelineEngine)
    engine.manager = type("Manager", (), {"db": DB()})()
    engine.cache = Cache()
    engine.scanner = Scanner()

    result = engine.refresh_open_position_prices()

    assert result == {
        "state": "REFRESHED",
        "open_positions": 2,
        "refreshed": 2,
        "failed": 0,
        "requests": 1,
        "bounded": True,
    }

    assert engine.cache.updated == [
        ("0xpool1", 1.25),
        ("0xpool2", 2.50),
    ]


def test_open_position_price_refresh_is_bounded():
    engine = PipelineEngine.__new__(PipelineEngine)
    engine.manager = type("Manager", (), {"db": DB()})()
    engine.cache = Cache()
    engine.scanner = Scanner()

    result = engine.refresh_open_position_prices(
        max_positions=1
    )

    assert result["refreshed"] == 1
    assert len(engine.cache.updated) == 1


def test_real_gecko_cache_pool_lookup_uses_tuple_row(tmp_path, monkeypatch):
    import app.cache.gecko_cache as module

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
        "name": "TOKEN/WBNB",
        "dex": "pancakeswap_v2",
        "liquidity": 10000,
        "volume_24h": 5000,
        "buys_24h": 20,
        "fdv": 50000,
        "price_usd": 1.0,
        "created_at": "2026-08-13T00:00:00Z",
    })

    assert cache.pool_for_token("0xtoken") == "0xpool"
