import json

from app.cache.analyzer_cache import AnalyzerCache
from app.pipeline.conveyor import (
    CACHE_COLD,
    CACHE_PARTIAL,
    CACHE_WARM,
    ConveyorLabeler,
)


TOKEN = "0x0000000000000000000000000000000000000001"


def row():
    return {
        "token": f"bsc_{TOKEN}",
        "liquidity": 10_000,
        "volume_24h": 5_000,
        "buys_24h": 20,
    }


def make_cache(tmp_path):
    return AnalyzerCache(
        tmp_path / "conveyor-cache.db"
    )


def payload(source):
    return json.dumps(
        {
            "success": True,
            "source": source,
            "data": {},
        }
    )


def test_conveyor_cold_when_all_cache_missing(tmp_path):
    cache = make_cache(tmp_path)
    conveyor = ConveyorLabeler(cache)

    result = conveyor.label(row())

    assert (
        result["conveyor"]["cache_state"]
        == CACHE_COLD
    )

    assert result["conveyor"]["missing_analyzers"] == [
        "token",
        "pair",
        "risk",
    ]

    cache.close()


def test_conveyor_partial_when_one_cache_hit(tmp_path):
    cache = make_cache(tmp_path)

    cache.set(
        "token",
        TOKEN.lower(),
        payload("token"),
    )

    conveyor = ConveyorLabeler(cache)

    result = conveyor.label(row())

    assert (
        result["conveyor"]["cache_state"]
        == CACHE_PARTIAL
    )

    assert result["conveyor"]["token_cache"] == "HIT"
    assert result["conveyor"]["pair_cache"] == "MISS"
    assert result["conveyor"]["risk_cache"] == "MISS"

    cache.close()


def test_conveyor_warm_when_all_cache_hit(tmp_path):
    cache = make_cache(tmp_path)

    for namespace in ("token", "pair", "risk"):
        cache.set(
            namespace,
            TOKEN.lower(),
            payload(namespace),
        )

    conveyor = ConveyorLabeler(cache)

    result = conveyor.label(row())

    assert (
        result["conveyor"]["cache_state"]
        == CACHE_WARM
    )

    assert (
        result["conveyor"]["missing_analyzers"]
        == []
    )

    cache.close()


def test_conveyor_batch_stats(tmp_path):
    cache = make_cache(tmp_path)
    conveyor = ConveyorLabeler(cache)

    rows = [
        {
            **row(),
            "token": (
                "bsc_0x000000000000000000000000"
                "0000000000000001"
            ),
        },
        {
            **row(),
            "token": (
                "bsc_0x000000000000000000000000"
                "0000000000000002"
            ),
        },
    ]

    result = conveyor.label_many(rows)

    assert result["stats"]["input"] == 2
    assert result["stats"]["cold"] == 2

    cache.close()
