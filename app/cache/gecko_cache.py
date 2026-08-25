import sqlite3
from pathlib import Path

DB = Path("data/cache/cache.db")


class GeckoCache:

    def __init__(self):

        DB.parent.mkdir(parents=True, exist_ok=True)

        self.db = sqlite3.connect(DB)

        self.db.execute("""

        CREATE TABLE IF NOT EXISTS gecko_pool_cache(

            pool TEXT PRIMARY KEY,

            token TEXT,

            quote_token TEXT,

            name TEXT,

            dex TEXT,

            liquidity REAL,

            volume24 REAL,

            buys24 INTEGER,

            fdv REAL,

            price_usd REAL DEFAULT 0,

            created_at TEXT,

            updated_at TEXT

        )

        """)

        columns = {
            row[1]
            for row in self.db.execute(
                "PRAGMA table_info(gecko_pool_cache)"
            )
        }

        if "quote_token" not in columns:
            self.db.execute(
                "ALTER TABLE gecko_pool_cache "
                "ADD COLUMN quote_token TEXT"
            )

        # Raw FACT history for calibration / future learning.
        # This never stores model scores or decision outputs.
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS market_observation_history(
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
        """)

        self.db.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_market_history_pool_source_time
        ON market_observation_history(
            pool,
            source,
            observed_at
        )
        """)

        self.db.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_market_history_token_time
        ON market_observation_history(
            token,
            observed_at
        )
        """)

        self.db.commit()

    def replace(self, row):

        self.db.execute("""

        INSERT OR REPLACE INTO gecko_pool_cache(

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

        """,(

            row["pool"],
            row["base_token"],
            row.get("quote_token"),
            row["name"],
            row["dex"],
            row["liquidity"],
            row["volume_24h"],
            row["buys_24h"],
            row["fdv"],
            row["price_usd"],
            row["created_at"]

        ))

        def canonical_address(value):
            value = str(
                value or ""
            ).strip().lower()

            if value.startswith("bsc_"):
                value = value[4:]

            return value or None

        source = str(
            row.get("source")
            or "geckoterminal"
        ).strip().lower()

        chain = str(
            row.get("chain")
            or "bsc"
        ).strip().lower()

        self.db.execute(
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
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                COALESCE(
                    ?,
                    strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    )
                ),
                strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            )
            """,
            (
                "MARKET_OBSERVATION_V1",
                chain,
                source,
                str(
                    row.get("dex")
                    or ""
                ).strip().lower()
                or None,
                canonical_address(
                    row.get("pool")
                ),
                canonical_address(
                    row.get("base_token")
                    or row.get("token")
                ),
                canonical_address(
                    row.get("quote_token")
                ),
                row.get("price_usd"),
                row.get("liquidity"),
                row.get("volume_24h"),
                row.get("buys_24h"),
                row.get("fdv"),
                row.get("market_cap"),
                row.get("created_at"),
                row.get("observed_at"),
            ),
        )

        self.db.commit()

    def history_for_pool(
        self,
        pool,
        *,
        source=None,
        limit=512,
    ):
        pool = str(
            pool or ""
        ).strip().lower()

        if not pool:
            return []

        limit = max(
            1,
            int(limit),
        )

        params = [pool]

        sql = """
            SELECT
                id,
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
            FROM market_observation_history
            WHERE lower(pool)=lower(?)
        """

        if source is not None:
            sql += """
                AND lower(source)=lower(?)
            """
            params.append(
                str(source).strip().lower()
            )

        sql += """
            ORDER BY id DESC
            LIMIT ?
        """

        params.append(limit)

        cur = self.db.execute(
            sql,
            tuple(params),
        )

        cols = [
            item[0]
            for item in cur.description
        ]

        rows = [
            dict(zip(cols, row))
            for row in cur.fetchall()
        ]

        rows.reverse()
        return rows

    def stream_math_calibration_for_pool(
        self,
        pool,
        *,
        source,
        limit=512,
    ):
        from app.risk.stream_stats import (
            calibrate_stream_math,
        )

        history = self.history_for_pool(
            pool,
            source=source,
            limit=limit,
        )

        return calibrate_stream_math(
            history
        )

    def observation_count(self):
        row = self.db.execute(
            """
            SELECT COUNT(*)
            FROM market_observation_history
            """
        ).fetchone()

        return int(row[0])

    def prune_except(self, pools, preserve_tokens=None):
        pools = list(dict.fromkeys(
            str(value or "").strip().lower()
            for value in pools
            if str(value or "").strip()
        ))

        preserve = list(dict.fromkeys(
            (
                str(value).strip().lower()
                if str(value).strip().lower().startswith("bsc_")
                else f"bsc_{str(value).strip().lower()}"
            )
            for value in (preserve_tokens or [])
            if str(value or "").strip()
        ))

        if not pools:
            return 0

        pool_marks = ",".join("?" for _ in pools)
        sql = (
            "DELETE FROM gecko_pool_cache "
            f"WHERE lower(pool) NOT IN ({pool_marks})"
        )
        params = list(pools)

        if preserve:
            token_marks = ",".join("?" for _ in preserve)
            sql += (
                f" AND lower(token) NOT IN ({token_marks})"
            )
            params.extend(preserve)

        cursor = self.db.execute(sql, params)
        self.db.commit()
        return cursor.rowcount

    def pool_for_token(self, token):
        row = self.db.execute(
            """
            SELECT pool
            FROM gecko_pool_cache
            WHERE lower(token)=lower(?)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (f"bsc_{token}",),
        ).fetchone()

        return row[0] if row else None

    def upsert_tracked_price(self, pool, token, price):
        pool = str(pool or "").strip().lower()
        token = str(token or "").strip().lower()
        price = float(price)

        if not pool or not token or price <= 0:
            raise ValueError("valid pool, token and price required")

        if not token.startswith("bsc_"):
            token = f"bsc_{token}"

        self.db.execute(
            """
            INSERT INTO gecko_pool_cache(
                pool,
                token,
                price_usd,
                updated_at
            )
            VALUES(?,?,?,datetime('now'))
            ON CONFLICT(pool) DO UPDATE SET
                token=excluded.token,
                price_usd=excluded.price_usd,
                updated_at=datetime('now')
            """,
            (pool, token, price),
        )

        self.db.commit()
        return True

    def update_pool_price(self, pool, price):
        price = float(price)

        if price <= 0:
            raise ValueError("price must be positive")

        cursor = self.db.execute(
            """
            UPDATE gecko_pool_cache
            SET price_usd=?,
                updated_at=datetime('now')
            WHERE lower(pool)=lower(?)
            """,
            (price, pool),
        )

        self.db.commit()
        return cursor.rowcount

    def all(self):

        cur=self.db.execute("""

        SELECT

        pool,
        token,
        quote_token,
        name,
        dex,
        liquidity,
        volume24 AS volume_24h,
        buys24 AS buys_24h,
        fdv,
        price_usd,
        created_at,
        updated_at

        FROM gecko_pool_cache

        ORDER BY liquidity DESC

        """)

        cols=[c[0] for c in cur.description]

        return [dict(zip(cols,row)) for row in cur.fetchall()]
