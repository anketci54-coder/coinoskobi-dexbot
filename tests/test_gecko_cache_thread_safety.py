import threading

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
