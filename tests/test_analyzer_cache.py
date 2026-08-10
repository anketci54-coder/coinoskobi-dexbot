import sqlite3

import app.cache.analyzer_cache as cache_module
from app.cache.analyzer_cache import AnalyzerCache


def test_cache_miss(tmp_path):
    cache = AnalyzerCache(
        tmp_path / "cache.db"
    )

    assert (
        cache.get(
            "token",
            "abc",
            ttl_seconds=60,
        )
        is None
    )

    assert cache.stats()["misses"] == 1

    cache.close()


def test_cache_hit(tmp_path):
    cache = AnalyzerCache(
        tmp_path / "cache.db"
    )

    cache.set(
        "token",
        "abc",
        '{"success": true}',
    )

    value = cache.get(
        "token",
        "abc",
        ttl_seconds=60,
    )

    assert value == '{"success": true}'
    assert cache.stats()["hits"] == 1

    cache.close()


def test_stale_cache_is_not_returned(
    tmp_path,
    monkeypatch,
):
    cache = AnalyzerCache(
        tmp_path / "cache.db"
    )

    monkeypatch.setattr(
        cache_module.AnalyzerCache,
        "_now",
        staticmethod(lambda: 1000),
    )

    cache.set(
        "risk",
        "abc",
        '{"safe": true}',
    )

    monkeypatch.setattr(
        cache_module.AnalyzerCache,
        "_now",
        staticmethod(lambda: 1100),
    )

    assert (
        cache.get(
            "risk",
            "abc",
            ttl_seconds=30,
        )
        is None
    )

    assert cache.stats()["stale"] == 1

    cache.close()


def test_cache_update_replaces_payload(
    tmp_path,
):
    cache = AnalyzerCache(
        tmp_path / "cache.db"
    )

    cache.set(
        "pair",
        "abc",
        '{"exists": false}',
    )

    cache.set(
        "pair",
        "abc",
        '{"exists": true}',
    )

    value = cache.get(
        "pair",
        "abc",
        ttl_seconds=60,
    )

    assert value == '{"exists": true}'

    cache.close()


def test_cache_namespace_isolated(
    tmp_path,
):
    cache = AnalyzerCache(
        tmp_path / "cache.db"
    )

    cache.set(
        "token",
        "abc",
        "TOKEN",
    )

    cache.set(
        "risk",
        "abc",
        "RISK",
    )

    assert (
        cache.get(
            "token",
            "abc",
            ttl_seconds=60,
        )
        == "TOKEN"
    )

    assert (
        cache.get(
            "risk",
            "abc",
            ttl_seconds=60,
        )
        == "RISK"
    )

    cache.close()


def test_cache_database_uses_wal(
    tmp_path,
):
    path = tmp_path / "cache.db"

    cache = AnalyzerCache(path)

    mode = cache.db.execute(
        "PRAGMA journal_mode"
    ).fetchone()[0]

    assert mode.lower() == "wal"

    cache.close()


def test_cache_schema_primary_key(
    tmp_path,
):
    path = tmp_path / "cache.db"

    cache = AnalyzerCache(path)

    rows = cache.db.execute(
        """
        PRAGMA table_info(
            analyzer_cache_v1
        )
        """
    ).fetchall()

    names = {
        row[1]
        for row in rows
    }

    assert {
        "namespace",
        "cache_key",
        "payload",
        "updated_at",
    }.issubset(names)

    cache.close()


def test_cache_delete(tmp_path):
    cache = AnalyzerCache(
        tmp_path / "cache.db"
    )

    cache.set(
        "token",
        "abc",
        "VALUE",
    )

    cache.delete(
        "token",
        "abc",
    )

    assert (
        cache.get(
            "token",
            "abc",
            ttl_seconds=60,
        )
        is None
    )

    cache.close()
