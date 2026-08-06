import sqlite3


class CachePrice:

    def __init__(self):
        self.db = sqlite3.connect("data/cache/cache.db")
        self.db.row_factory = sqlite3.Row

    def get_price(self, token):

        row = self.db.execute(
            """
            SELECT price_usd
            FROM gecko_pool_cache
            WHERE lower(token)=lower(?)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (f"bsc_{token}",)
        ).fetchone()

        if row is None:
            raise RuntimeError(f"Cache fiyatı bulunamadı : {token}")

        return float(row["price_usd"])
