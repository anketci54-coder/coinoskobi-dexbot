import sqlite3

from app.market_data.broker import MarketDataBroker


class _SnapshotClient:
    def __init__(self):
        self.calls = []

    def fetch(self, pools):
        self.calls.append(list(pools))
        return []


def _cache_db(path, rows):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE gecko_pool_cache(pool TEXT PRIMARY KEY, dex TEXT)")
    db.executemany("INSERT INTO gecko_pool_cache(pool, dex) VALUES(?, ?)", rows)
    db.commit()
    db.close()


def test_broker_resolves_legacy_pool_address_from_cache(tmp_path):
    cache = tmp_path / "cache.db"
    _cache_db(cache, [("0xpool", "pancakeswap_v3")])
    client = _SnapshotClient()
    broker = MarketDataBroker(snapshot_client=client, identity_db_path=cache)
    broker.pool_snapshots(["0xpool"], max_pools=1)
    assert client.calls == [[{"pool": "0xpool", "dex": "pancakeswap_v3"}]]


def test_broker_preserves_explicit_pool_identity(tmp_path):
    cache = tmp_path / "cache.db"
    _cache_db(cache, [("0xpool", "pancakeswap_v2")])
    client = _SnapshotClient()
    broker = MarketDataBroker(snapshot_client=client, identity_db_path=cache)
    broker.pool_snapshots([{"pool": "0xpool", "dex": "pancakeswap_v3"}], max_pools=1)
    assert client.calls == [[{"pool": "0xpool", "dex": "pancakeswap_v3"}]]


def test_broker_fails_closed_when_legacy_pool_identity_is_unknown(tmp_path):
    cache = tmp_path / "cache.db"
    _cache_db(cache, [])
    client = _SnapshotClient()
    broker = MarketDataBroker(snapshot_client=client, identity_db_path=cache)
    try:
        broker.pool_snapshots(["0xmissing"], max_pools=1)
    except ValueError as exc:
        assert str(exc) == "pool identity mapping required"
    else:
        raise AssertionError("unknown pool identity must fail closed")
    assert client.calls == []
