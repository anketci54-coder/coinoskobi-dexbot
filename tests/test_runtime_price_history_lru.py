from app.pipeline import engine as engine_module
from app.pipeline.runtime_price_history import RuntimePriceHistory


def test_existing_key_refreshes_lru_position():
    cache = RuntimePriceHistory(max_entries=2)

    cache.setdefault(("0xa", "0x1", "PAIR_ONCHAIN"), [])
    cache.setdefault(("0xb", "0x2", "PAIR_ONCHAIN"), [])

    refreshed = cache.setdefault(
        ("0xa", "0x1", "PAIR_ONCHAIN"),
        [],
    )
    refreshed.append(1.0)

    cache.setdefault(("0xc", "0x3", "PAIR_ONCHAIN"), [])

    assert ("0xa", "0x1", "PAIR_ONCHAIN") in cache
    assert ("0xb", "0x2", "PAIR_ONCHAIN") not in cache
    assert ("0xc", "0x3", "PAIR_ONCHAIN") in cache


def test_watched_pair_is_protected_from_ordinary_eviction():
    watched = {
        "0xa": "0x1",
    }

    cache = RuntimePriceHistory(
        max_entries=2,
        watch_snapshot=lambda: dict(watched),
    )

    cache.setdefault(("0xa", "0x1", "PAIR_ONCHAIN"), [])
    cache.setdefault(("0xb", "0x2", "PAIR_ONCHAIN"), [])
    cache.setdefault(("0xc", "0x3", "PAIR_ONCHAIN"), [])

    assert ("0xa", "0x1", "PAIR_ONCHAIN") in cache
    assert ("0xb", "0x2", "PAIR_ONCHAIN") not in cache
    assert ("0xc", "0x3", "PAIR_ONCHAIN") in cache


def test_runtime_math_history_grows_across_revisit():
    original = engine_module._RUNTIME_PRICE_HISTORY
    cache = RuntimePriceHistory(max_entries=2048)
    engine_module._RUNTIME_PRICE_HISTORY = cache

    common = {
        "token_address": "0xtoken",
        "pool": "0xpool",
        "exit_evidence": {},
        "lp_evidence": {},
        "market_context": {},
        "sellability_data": {},
    }

    try:
        first = engine_module._runtime_math_evidence(
            **common,
            price=1.0,
            upstream_price_series=[1.0, 1.0, 1.0, 1.0],
            price_series_source="PAIR_RUNTIME_ONCHAIN",
        )

        second = engine_module._runtime_math_evidence(
            **common,
            price=1.1,
            upstream_price_series=[1.1, 1.1, 1.1, 1.1],
            price_series_source="PAIR_RUNTIME_ONCHAIN",
        )

        assert first["price_series"] == [
            1.0,
            1.0,
            1.0,
            1.0,
        ]
        assert second["price_series"] == [
            1.0,
            1.0,
            1.0,
            1.0,
            1.1,
        ]
    finally:
        engine_module._RUNTIME_PRICE_HISTORY = original


def test_cache_remains_bounded_when_all_entries_are_watched():
    watched = {
        "0xa": "0x1",
        "0xb": "0x2",
        "0xc": "0x3",
    }

    cache = RuntimePriceHistory(
        max_entries=2,
        watch_snapshot=lambda: dict(watched),
    )

    cache.setdefault(("0xa", "0x1", "PAIR_ONCHAIN"), [])
    cache.setdefault(("0xb", "0x2", "PAIR_ONCHAIN"), [])
    cache.setdefault(("0xc", "0x3", "PAIR_ONCHAIN"), [])

    assert len(cache) == 2
