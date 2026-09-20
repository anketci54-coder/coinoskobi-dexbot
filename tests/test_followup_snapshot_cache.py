import sqlite3
import time

import pytest

from app.scanner.followup_snapshot_cache import (
    persist_registered_followup_snapshots,
)
from app.learning.counterfactual_observation import CounterfactualObservationStore


def _db(path):
    db = sqlite3.connect(path)

    db.execute(
        """
        CREATE TABLE gecko_pool_cache(
            pool TEXT PRIMARY KEY,
            token TEXT,
            quote_token TEXT,
            name TEXT,
            dex TEXT,
            liquidity REAL,
            volume24 REAL,
            buys24 INTEGER,
            fdv REAL,
            price_usd REAL,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    db.execute(
        """
        CREATE TABLE candidate_followup_registry(
            pool TEXT PRIMARY KEY,
            token TEXT NOT NULL,
            expires_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )

    db.execute(
        """
        CREATE TABLE market_observation_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_version TEXT NOT NULL,
            chain TEXT NOT NULL,
            source TEXT NOT NULL,
            dex TEXT,
            pool TEXT NOT NULL,
            token TEXT,
            quote_token TEXT,
            price_usd REAL,
            liquidity_usd REAL,
            volume_24h REAL,
            buys_24h INTEGER,
            fdv_usd REAL,
            market_cap_usd REAL,
            pool_created_at TEXT,
            observed_at TEXT NOT NULL,
            ingested_at TEXT NOT NULL
        )
        """
    )

    return db


def test_followup_prune_guard_uses_normalized_pool_index(tmp_path):
    path = tmp_path / "cache.db"
    db = _db(path)
    store = CounterfactualObservationStore.__new__(CounterfactualObservationStore)
    store._cache_db_path = str(path)
    try:
        assert store._ensure_cache_followup_registry() is True
        db.executemany(
            "INSERT INTO candidate_followup_registry VALUES(?,?,?,?)",
            [(f"0xpool{i}", f"token{i}", 200, 100) for i in range(2000)],
        )
        db.execute("ANALYZE candidate_followup_registry")
        plan = db.execute("""
            EXPLAIN QUERY PLAN
            SELECT 1 FROM candidate_followup_registry r
            WHERE lower(r.pool)=lower(?) AND r.expires_at > unixepoch()
        """, ("0xpool",)).fetchall()
        assert any("idx_candidate_followup_pool_expiry" in row[3] for row in plan)
    finally:
        db.close()


def test_failed_followup_history_closes_connection_and_releases_cache_writer(tmp_path, monkeypatch):
    path = tmp_path / "cache.db"
    db = _db(path)
    db.execute("INSERT INTO gecko_pool_cache(pool, token, price_usd) VALUES('pool', 'token', 1)")
    db.execute("INSERT INTO candidate_followup_registry VALUES('pool', 'token', 200, 100)")
    db.execute("""CREATE TRIGGER reject_history BEFORE INSERT
        ON market_observation_history BEGIN SELECT RAISE(ABORT, 'history failed'); END""")
    db.commit()
    original_connect = sqlite3.connect
    connections = []
    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connections.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        result = persist_registered_followup_snapshots(
            [{"pool": "pool", "base_token": "token", "price_usd": 2}],
            db_path=path, now=100,
        )
        assert result == {"state": "DB_ERROR", "updated": 0, "history": 0}
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connections[0].execute("SELECT 1")
        assert db.execute("SELECT price_usd FROM gecko_pool_cache").fetchone()[0] == 1
        db.execute("PRAGMA busy_timeout=100")
        db.execute("UPDATE gecko_pool_cache SET price_usd=3")
        db.commit()
    finally:
        db.close()
        for connection in connections:
            connection.close()


@pytest.mark.parametrize("operation", ["register", "sync"])
def test_counterfactual_cache_error_always_closes_connection(tmp_path, monkeypatch, operation):
    path = tmp_path / "cache.db"
    db = _db(path)
    db.execute("INSERT INTO gecko_pool_cache(pool, token, price_usd) VALUES('pool', 'token', 1)")
    table, event = ("candidate_followup_registry", "INSERT") if operation == "register" else ("gecko_pool_cache", "UPDATE")
    db.execute(f"""CREATE TRIGGER reject_write BEFORE {event} ON {table}
        BEGIN SELECT RAISE(ABORT, 'rejected'); END""")
    db.commit()
    store = CounterfactualObservationStore.__new__(CounterfactualObservationStore)
    store._cache_db_path = str(path)
    store._db = sqlite3.connect(":memory:")
    store._db.execute("CREATE TABLE counterfactual_observations(pool, token, completed_at)")
    store._db.execute("INSERT INTO counterfactual_observations VALUES('pool', 'token', NULL)")
    original_connect = sqlite3.connect
    connections = []
    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connections.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        if operation == "register":
            assert store._register_followup(token="token", pool="pool", observed_at=100) is False
        else:
            assert store._sync_exact_pool_cache_price(token="token::pool::pool", current_price=2) == 0
        for connection in connections:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                connection.execute("SELECT 1")
        db.execute("PRAGMA busy_timeout=100")
        db.execute("INSERT INTO gecko_pool_cache(pool, token, price_usd) VALUES('other', 'other', 3)")
        db.commit()
    finally:
        store._db.close()
        db.close()
        for connection in connections:
            connection.close()


def test_only_registered_followup_pool_gets_fresh_market_snapshot(
    tmp_path,
):
    path = tmp_path / "cache.db"
    now = time.time()
    db = _db(path)

    for pool, token in (
        ("0xtracked", "bsc_0xtoken1"),
        ("0xother", "bsc_0xtoken2"),
    ):
        db.execute(
            """
            INSERT INTO gecko_pool_cache(
                pool,
                token,
                quote_token,
                name,
                dex,
                liquidity,
                volume24,
                buys24,
                fdv,
                price_usd,
                created_at,
                updated_at
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            """,
            (
                pool,
                token,
                "bsc_0xoldquote",
                "OLD",
                "pancakeswap_v2",
                100.0,
                200.0,
                3,
                400.0,
                1.0,
                "2026-08-24T00:00:00Z",
            ),
        )

    db.execute(
        """
        INSERT INTO candidate_followup_registry(
            pool, token, expires_at, updated_at
        ) VALUES(?,?,?,?)
        """,
        (
            "0xtracked",
            "0xtoken1",
            now + 3600,
            now,
        ),
    )
    db.commit()
    db.close()

    # Mirrors the real Gecko exact-pool parser: no synthetic
    # observed_at field is required from the provider payload.
    result = persist_registered_followup_snapshots(
        [
            {
                "pool": "0xtracked",
                "base_token": "bsc_0xtoken1",
                "quote_token": "bsc_0xquote1",
                "name": "TOKEN1 / WBNB",
                "dex": "pancakeswap_v2",
                "price_usd": 2.5,
                "liquidity": 250000.0,
                "volume_24h": 750000.0,
                "buys_24h": 321,
                "fdv": 1250000.0,
                "market_cap": 1000000.0,
                "created_at": "2026-08-25T00:00:00Z",
            },
            {
                "pool": "0xother",
                "base_token": "bsc_0xtoken2",
                "quote_token": "bsc_0xquote2",
                "name": "TOKEN2 / WBNB",
                "dex": "pancakeswap_v2",
                "price_usd": 9.0,
                "liquidity": 999999.0,
                "volume_24h": 999999.0,
                "buys_24h": 999,
                "fdv": 9999999.0,
                "market_cap": 9999999.0,
                "created_at": "2026-08-25T00:00:00Z",
            },
        ],
        db_path=path,
        now=now,
    )

    assert result == {
        "state": "UPDATED",
        "updated": 1,
        "history": 1,
    }

    db = sqlite3.connect(path)

    tracked = db.execute(
        """
        SELECT
            token,
            quote_token,
            name,
            liquidity,
            volume24,
            buys24,
            fdv,
            price_usd
        FROM gecko_pool_cache
        WHERE pool='0xtracked'
        """
    ).fetchone()

    other = db.execute(
        """
        SELECT liquidity, volume24, buys24, price_usd
        FROM gecko_pool_cache
        WHERE pool='0xother'
        """
    ).fetchone()

    history = db.execute(
        """
        SELECT
            source,
            pool,
            price_usd,
            liquidity_usd,
            volume_24h,
            buys_24h,
            observed_at
        FROM market_observation_history
        """
    ).fetchall()

    db.close()

    assert tracked == (
        "bsc_0xtoken1",
        "bsc_0xquote1",
        "TOKEN1 / WBNB",
        250000.0,
        750000.0,
        321,
        1250000.0,
        2.5,
    )

    assert other == (
        100.0,
        200.0,
        3,
        1.0,
    )

    assert len(history) == 1
    assert history[0][:6] == (
        "geckoterminal_followup",
        "0xtracked",
        2.5,
        250000.0,
        750000.0,
        321,
    )
    assert history[0][6]


def test_canonical_snapshot_fields_and_provider_source_are_persisted(tmp_path):
    path = tmp_path / "cache.db"
    db = _db(path)

    db.execute(
        """
        INSERT INTO gecko_pool_cache(
            pool, token, dex, price_usd, updated_at
        )
        VALUES(
            '0xtracked',
            'bsc_0xtoken1',
            'pancakeswap_v2',
            1.0,
            datetime('now')
        )
        """
    )
    db.execute(
        """
        INSERT INTO candidate_followup_registry(
            pool, token, expires_at, updated_at
        )
        VALUES('0xtracked','0xtoken1',200,100)
        """
    )
    db.commit()
    db.close()

    result = persist_registered_followup_snapshots(
        [{
            "schema_version": "DEXSCREENER_SNAPSHOT_V1",
            "source": "dexscreener",
            "pool": "0xtracked",
            "base_token": "0xtoken1",
            "quote_token": "0xquote1",
            "display_name": "TOKEN1 / WBNB",
            "dex": "pancakeswap_v2",
            "price_usd": 2.5,
            "liquidity_usd": 250000.0,
            "volume_h24_usd": 750000.0,
            "buys_h24": 321,
            "sells_h24": 123,
            "fdv_usd": 1250000.0,
            "market_cap_usd": 1000000.0,
            "pair_created_at_ms": 1780000000000,
            "observed_at": "2026-09-20T17:30:07+00:00",
        }],
        db_path=path,
        now=100,
    )

    assert result == {
        "state": "UPDATED",
        "updated": 1,
        "history": 1,
    }

    db = sqlite3.connect(path)

    cache_row = db.execute(
        """
        SELECT
            liquidity,
            volume24,
            buys24,
            sells24,
            fdv,
            price_usd
        FROM gecko_pool_cache
        WHERE pool='0xtracked'
        """
    ).fetchone()

    history_row = db.execute(
        """
        SELECT
            source,
            liquidity_usd,
            volume_24h,
            buys_24h,
            sells_24h,
            fdv_usd,
            market_cap_usd,
            price_usd
        FROM market_observation_history
        WHERE pool='0xtracked'
        """
    ).fetchone()

    db.close()

    assert cache_row == (
        250000.0,
        750000.0,
        321,
        123,
        1250000.0,
        2.5,
    )

    assert history_row == (
        "dexscreener",
        250000.0,
        750000.0,
        321,
        123,
        1250000.0,
        1000000.0,
        2.5,
    )
