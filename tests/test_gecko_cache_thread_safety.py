import threading
import sqlite3
import time

import pytest

from app.cache import gecko_cache as module


def test_gecko_cache_allows_cross_thread_price_refresh(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()
    cache.upsert_tracked_price(
        "0xpool",
        "0xtoken",
        1.0,
    )

    errors = []

    def worker():
        try:
            cache.update_pool_price(
                "0xpool",
                2.0,
            )
            cache.all()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(
        target=worker
    )
    thread.start()
    thread.join(timeout=1.0)

    assert thread.is_alive() is False
    assert errors == []

    rows = cache.all()
    assert len(rows) == 1
    assert rows[0]["price_usd"] == 2.0


def test_failed_history_write_rolls_back_and_releases_writer(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "DB", tmp_path / "cache.db")
    cache = module.GeckoCache()
    other = module.GeckoCache()
    try:
        cache.db.execute("""CREATE TRIGGER reject_history BEFORE INSERT
            ON market_observation_history BEGIN
            SELECT RAISE(ABORT, 'history unavailable'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="history unavailable"):
            cache.replace({
                "pool": "pool", "base_token": "token", "name": "TOKEN",
                "dex": "pancakeswap_v2", "liquidity": 1000,
                "volume_24h": 100, "buys_24h": 1, "fdv": 10000,
                "price_usd": 1, "created_at": None,
            })
        assert not cache.db.in_transaction
        assert cache.all() == []
        other.db.execute("PRAGMA busy_timeout=50")
        assert other.upsert_tracked_price("pool", "token", 2)
        assert cache.all()[0]["price_usd"] == 2
    finally:
        cache.db.close()
        other.db.close()


@pytest.mark.parametrize("operation", ["update", "upsert"])
def test_price_write_lock_wait_is_bounded_and_timeout_restored(monkeypatch, tmp_path, operation):
    monkeypatch.setattr(module, "DB", tmp_path / "cache.db")
    cache = module.GeckoCache()
    other = module.GeckoCache()
    try:
        other.db.execute("BEGIN IMMEDIATE")
        start = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            if operation == "update":
                cache.update_pool_price("pool", 2)
            else:
                cache.upsert_tracked_price("pool", "token", 2)
        assert time.monotonic() - start < 2
        assert not cache.db.in_transaction
        assert cache.db.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        other.db.rollback()
        assert cache.upsert_tracked_price("pool", "token", 3)
    finally:
        other.db.close()
        cache.db.close()
