import sqlite3
import threading
from pathlib import Path


DB = Path("data/cache/cache.db")


class CachePrice:

    def __init__(self, db_path=None):
        self.db = sqlite3.connect(
            db_path or DB,
            check_same_thread=False,
        )
        self.db.row_factory = sqlite3.Row
        self._lock = threading.RLock()

    def get_price(self, token):
        with self._lock:
            row = self.db.execute(
                """
                SELECT price_usd
                FROM gecko_pool_cache
                WHERE lower(token)=lower(?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (f"bsc_{token}",),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Cache fiyatı bulunamadı : {token}"
            )

        price = float(row["price_usd"])

        if price <= 0:
            raise RuntimeError(
                f"Cache fiyatı geçersiz : {token}"
            )

        return price
