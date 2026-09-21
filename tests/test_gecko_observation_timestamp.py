from datetime import datetime, timezone

from app.cache import gecko_cache as cache_module
from app.learning.economic_probe import _observation_epoch
from app.pipeline.engine import _runtime_observation_epoch
from app.pipeline.engine import PipelineEngine
from app.learning.counterfactual_observation import CounterfactualObservationStore
from app.scanner.adapters.source_router import normalize_source_rows


def test_cache_round_trip_preserves_source_observation_time(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cache_module, "DB", tmp_path / "cache.db")
    timestamp = "2026-09-21T08:15:30.125000+00:00"
    cache = cache_module.GeckoCache()
    try:
        cache.replace({
            "pool": "0xpool", "base_token": "0xtoken",
            "quote_token": "0xquote", "name": "TOKEN",
            "dex": "pancakeswap_v2", "liquidity": 1000,
            "volume_24h": 100, "buys_24h": 1, "sells_24h": 1,
            "fdv": 10000, "price_usd": 1.25,
            "created_at": None, "observed_at": timestamp,
        })

        cached = cache.all()[0]
        assert cached["observed_at"] == timestamp
        history = cache.history_for_pool("0xpool", limit=1)[0]
        assert history["observed_at"] == timestamp

        candidate = normalize_source_rows(
            "geckoterminal", "bsc", [cached]
        )["candidates"][0]
        assert candidate.to_dict()["observed_at"] == timestamp
        assert _runtime_observation_epoch(timestamp) == datetime.fromisoformat(
            timestamp
        ).replace(tzinfo=timezone.utc).timestamp()
    finally:
        cache.db.close()


def test_existing_gecko_cache_migrates_observed_at_column(
    monkeypatch, tmp_path
):
    import sqlite3

    db_path = tmp_path / "legacy.db"
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE gecko_pool_cache(
        pool TEXT PRIMARY KEY, token TEXT, name TEXT, dex TEXT,
        liquidity REAL, volume24 REAL, buys24 INTEGER, fdv REAL,
        price_usd REAL, created_at TEXT, updated_at TEXT
    )""")
    db.commit()
    db.close()

    monkeypatch.setattr(cache_module, "DB", db_path)
    cache = cache_module.GeckoCache()
    try:
        columns = {
            row[1] for row in cache.db.execute(
                "PRAGMA table_info(gecko_pool_cache)"
            )
        }
        assert "observed_at" in columns
        assert cache.all() == []
    finally:
        cache.db.close()


def test_runtime_timestamp_parser_accepts_scanner_iso_time():
    timestamp = "2026-09-21T08:15:30.125000+00:00"
    assert _runtime_observation_epoch(timestamp) > 0
    assert _observation_epoch(timestamp) == _runtime_observation_epoch(
        timestamp
    )


def test_cached_scanner_observation_enters_counterfactual_analysis():
    timestamp = "2026-09-21T08:15:30.125000+00:00"
    cached_row = {
        "pool": "0xpool", "token": "0xtoken", "price_usd": 1.25,
        "observed_at": timestamp,
    }
    candidate = normalize_source_rows(
        "geckoterminal", "bsc", [cached_row]
    )["candidates"][0].to_dict()
    engine = PipelineEngine.__new__(PipelineEngine)
    engine.counterfactual_store = CounterfactualObservationStore()

    result = engine.observe_counterfactual_candidate(
        candidate, {"paper": "WATCH"}
    )

    assert result["evaluation"]["state"] != "INVALID_OBSERVATION_TIME"
    assert result["record"]["state"] == "RECORDED"
