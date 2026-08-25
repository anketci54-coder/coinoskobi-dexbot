import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


CACHE_DB = Path("data/cache/cache.db")


def _canonical(value):
    value = str(value or "").strip().lower()
    if value.startswith("bsc_"):
        value = value[4:]
    return value


def persist_registered_followup_snapshots(
    snapshots,
    *,
    db_path=CACHE_DB,
    now=None,
):
    """
    Persist fresh provider facts only for pools already registered by the
    counterfactual reevaluation ledger.

    This is ingestion/cache maintenance only. It has no decision, paper,
    live, wallet, signing or execution authority.
    """
    path = Path(db_path)
    if not path.exists():
        return {
            "state": "CACHE_MISSING",
            "updated": 0,
            "history": 0,
        }

    rows = [
        dict(row)
        for row in (snapshots or [])
        if isinstance(row, dict)
    ]

    if not rows:
        return {
            "state": "EMPTY",
            "updated": 0,
            "history": 0,
        }

    timestamp = float(
        time.time()
        if now is None
        else now
    )
    fallback_observed_at = (
        datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat()
    )

    try:
        db = sqlite3.connect(path, timeout=5)
        db.execute("PRAGMA busy_timeout=5000;")

        registry_exists = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name='candidate_followup_registry'
            """
        ).fetchone()

        cache_exists = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name='gecko_pool_cache'
            """
        ).fetchone()

        if registry_exists is None or cache_exists is None:
            db.close()
            return {
                "state": "REGISTRY_UNAVAILABLE",
                "updated": 0,
                "history": 0,
            }

        history_exists = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name='market_observation_history'
            """
        ).fetchone()

        updated = 0
        history = 0

        for row in rows:
            pool = _canonical(row.get("pool"))
            if not pool:
                continue

            tracked = db.execute(
                """
                SELECT token
                FROM candidate_followup_registry
                WHERE lower(pool)=lower(?)
                  AND expires_at > ?
                """,
                (pool, timestamp),
            ).fetchone()

            if tracked is None:
                continue

            token = _canonical(
                row.get("base_token")
                or row.get("token")
                or tracked[0]
            )
            quote = _canonical(
                row.get("quote_token")
            )

            if not token:
                token = _canonical(tracked[0])

            token_db = (
                f"bsc_{token}"
                if token
                else None
            )
            quote_db = (
                f"bsc_{quote}"
                if quote
                else None
            )

            cursor = db.execute(
                """
                UPDATE gecko_pool_cache
                SET token=COALESCE(?, token),
                    quote_token=COALESCE(?, quote_token),
                    name=COALESCE(?, name),
                    dex=COALESCE(?, dex),
                    liquidity=COALESCE(?, liquidity),
                    volume24=COALESCE(?, volume24),
                    buys24=COALESCE(?, buys24),
                    fdv=COALESCE(?, fdv),
                    price_usd=COALESCE(?, price_usd),
                    created_at=COALESCE(?, created_at),
                    updated_at=datetime('now')
                WHERE lower(pool)=lower(?)
                """,
                (
                    token_db,
                    quote_db,
                    row.get("name"),
                    row.get("dex"),
                    row.get("liquidity"),
                    row.get("volume_24h"),
                    row.get("buys_24h"),
                    row.get("fdv"),
                    row.get("price_usd"),
                    row.get("created_at"),
                    pool,
                ),
            )

            updated += int(cursor.rowcount or 0)

            if history_exists is not None:
                db.execute(
                    """
                    INSERT INTO market_observation_history(
                        schema_version,
                        chain,
                        source,
                        dex,
                        pool,
                        token,
                        quote_token,
                        price_usd,
                        liquidity_usd,
                        volume_24h,
                        buys_24h,
                        fdv_usd,
                        market_cap_usd,
                        pool_created_at,
                        observed_at,
                        ingested_at
                    )
                    VALUES(
                        'MARKET_OBSERVATION_V1',
                        'bsc',
                        'geckoterminal_followup',
                        ?,?,?,?,?,?,?,?,?,?,?,?,
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    )
                    """,
                    (
                        row.get("dex"),
                        pool,
                        token or None,
                        quote or None,
                        row.get("price_usd"),
                        row.get("liquidity"),
                        row.get("volume_24h"),
                        row.get("buys_24h"),
                        row.get("fdv"),
                        row.get("market_cap"),
                        row.get("created_at"),
                        (
                            row.get("observed_at")
                            or fallback_observed_at
                        ),
                    ),
                )
                history += 1

        db.commit()
        db.close()

        return {
            "state": "UPDATED",
            "updated": updated,
            "history": history,
        }

    except sqlite3.Error:
        return {
            "state": "DB_ERROR",
            "updated": 0,
            "history": 0,
        }
