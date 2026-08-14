import sqlite3
from concurrent.futures import ThreadPoolExecutor

from app.paper.cache_price import CachePrice


def test_cache_price_supports_worker_threads(tmp_path):
    path = tmp_path / "cache.db"

    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE gecko_pool_cache(
                token TEXT,
                price_usd REAL,
                updated_at TEXT
            )
        """)
        conn.execute("""
            INSERT INTO gecko_pool_cache
            VALUES(
                'bsc_0xtoken',
                1.25,
                datetime('now')
            )
        """)

    reader = CachePrice(db_path=path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        prices = list(
            pool.map(
                lambda _: reader.get_price("0xtoken"),
                range(32),
            )
        )

    assert prices == [1.25] * 32
