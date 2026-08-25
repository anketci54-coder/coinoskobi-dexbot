import sqlite3
import time

from app.scanner.followup_snapshot_cache import (
    persist_registered_followup_snapshots,
)


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
                "observed_at": "2026-08-25T12:00:00Z",
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
                "observed_at": "2026-08-25T12:00:00Z",
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
            buys_24h
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

    assert history == [
        (
            "geckoterminal_followup",
            "0xtracked",
            2.5,
            250000.0,
            750000.0,
            321,
        )
    ]
