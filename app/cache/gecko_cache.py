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

        self.db.commit()

    def replace(self, row):

        self.db.execute("""

        INSERT OR REPLACE INTO gecko_pool_cache(

            pool,
            token,
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

        VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now'))

        """,(

            row["pool"],
            row["base_token"],
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

    def all(self):

        cur=self.db.execute("""

        SELECT

        pool,
        token,
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
