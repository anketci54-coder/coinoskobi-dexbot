import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB = Path("data/cache/cache.db")


class AnalyzerCache:

    def __init__(self, db_path=DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.db = sqlite3.connect(
            self.db_path,
            timeout=5,
        )

        self.db.execute(
            "PRAGMA journal_mode=WAL"
        )

        self.db.execute(
            "PRAGMA synchronous=NORMAL"
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS analyzer_cache_v1(
                namespace TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY(namespace, cache_key)
            )
            """
        )

        self.db.commit()

        self.hits = 0
        self.misses = 0
        self.stale = 0
        self.writes = 0

    @staticmethod
    def _now():
        return datetime.now(
            timezone.utc
        ).timestamp()

    def get(
        self,
        namespace,
        cache_key,
        ttl_seconds,
    ):
        row = self.db.execute(
            """
            SELECT payload, updated_at
            FROM analyzer_cache_v1
            WHERE namespace = ?
              AND cache_key = ?
            """,
            (
                namespace,
                cache_key,
            ),
        ).fetchone()

        if row is None:
            self.misses += 1
            return None

        payload, updated_at = row

        age = self._now() - float(
            updated_at
        )

        if age < 0:
            age = 0

        if age > ttl_seconds:
            self.stale += 1
            return None

        self.hits += 1

        return payload

    def set(
        self,
        namespace,
        cache_key,
        payload,
    ):
        self.db.execute(
            """
            INSERT INTO analyzer_cache_v1(
                namespace,
                cache_key,
                payload,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(namespace, cache_key)
            DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                namespace,
                cache_key,
                payload,
                self._now(),
            ),
        )

        self.db.commit()
        self.writes += 1

    def delete(
        self,
        namespace,
        cache_key,
    ):
        self.db.execute(
            """
            DELETE FROM analyzer_cache_v1
            WHERE namespace = ?
              AND cache_key = ?
            """,
            (
                namespace,
                cache_key,
            ),
        )

        self.db.commit()

    def stats(self):
        return {
            "hits": self.hits,
            "misses": self.misses,
            "stale": self.stale,
            "writes": self.writes,
        }

    def close(self):
        self.db.close()
