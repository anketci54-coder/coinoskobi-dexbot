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

        self.db.commit()

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
