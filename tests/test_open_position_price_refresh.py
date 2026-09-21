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


def test_open_position_full_snapshot_preserves_provider_provenance():
    class SnapshotDB:
        def open_positions(self):
            return [{
                "token": "0xtoken1",
                "pool": "0xpool1",
                "dex": "pancakeswap_v2",
            }]

    class SnapshotCache:
        def __init__(self):
            self.updated = []
            self.observations = []

        def record_market_observation(
            self,
            row,
        ):
            self.observations.append(
                dict(row)
            )
            return True

        def update_pool_price(
            self,
            pool,
            price,
        ):
            self.updated.append(
                (pool, price)
            )
            return 1

    class SnapshotScanner:
        def pool_snapshots(
            self,
            pools,
            *,
            persist_followups=True,
        ):
            assert persist_followups is False
            assert pools == ["0xpool1"]

            return [{
                "schema_version": (
                    "DEXSCREENER_SNAPSHOT_V1"
                ),
                "chain": "bsc",
                "source": "dexscreener",
                "dex": "pancakeswap_v2",
                "pool": "0xpool1",
                "base_token": "0xtoken1",
                "quote_token": "0xquote",
                "price_usd": 0.000123,
                "liquidity_usd": 45678.0,
                "fdv_usd": 123456.0,
                "market_cap_usd": 120000.0,
                "volume_h24_usd": 9876.0,
                "buys_h24": 55,
                "sells_h24": 21,
                "observed_at": (
                    "2026-09-21T11:04:00+00:00"
                ),
            }]

    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    engine.manager = type(
        "Manager",
        (),
        {"db": SnapshotDB()},
    )()

    engine.cache = SnapshotCache()
    engine.scanner = SnapshotScanner()

    result = (
        engine.refresh_open_position_prices()
    )

    assert result == {
        "state": "REFRESHED",
        "open_positions": 1,
        "refreshed": 1,
        "failed": 0,
        "requests": 1,
        "bounded": True,
    }

    assert engine.cache.updated == [
        ("0xpool1", 0.000123)
    ]

    assert len(
        engine.cache.observations
    ) == 1

    observation = (
        engine.cache.observations[0]
    )

    assert observation["pool"] == (
        "0xpool1"
    )
    assert observation["source"] == (
        "dexscreener"
    )
    assert observation["price_usd"] == (
        0.000123
    )
    assert observation[
        "liquidity_usd"
    ] == 45678.0
    assert observation["fdv_usd"] == (
        123456.0
    )
    assert observation[
        "observed_at"
    ] == "2026-09-21T11:04:00+00:00"
