import sqlite3
import threading
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

        # Analyzer instances are module-level singletons while candidate
        # analysis runs inside WorkScheduler worker threads. The cache
        # connection therefore has to be explicitly shareable, and every
        # operation on that connection must be serialized by this instance.
        self._lock = threading.RLock()

        self.db = sqlite3.connect(
            self.db_path,
            timeout=5,
            check_same_thread=False,
        )

        with self._lock:
            self.db.execute(
                "PRAGMA journal_mode=WAL"
            )

            self.db.execute(
                "PRAGMA synchronous=NORMAL"
            )

            self.db.execute(
                "PRAGMA busy_timeout=5000"
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

    def get_versioned(
        self,
        namespace,
        cache_key,
        ttl_seconds,
    ):
        """Return a fresh payload with the exact cache version timestamp."""
        with self._lock:
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
            return {
                "payload": payload,
                "updated_at": float(updated_at),
            }

    def get(
        self,
        namespace,
        cache_key,
        ttl_seconds,
    ):
        versioned = self.get_versioned(
            namespace,
            cache_key,
            ttl_seconds,
        )
        if versioned is None:
            return None
        return versioned["payload"]

    def set(
        self,
        namespace,
        cache_key,
        payload,
    ):
        with self._lock:
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

    def replace_payload_preserve_age(
        self,
        namespace,
        cache_key,
        payload,
    ):
        """Replace a cached payload without extending its provider TTL."""
        with self._lock:
            cursor = self.db.execute(
                """
                UPDATE analyzer_cache_v1
                SET payload = ?
                WHERE namespace = ?
                  AND cache_key = ?
                """,
                (
                    payload,
                    namespace,
                    cache_key,
                ),
            )

            self.db.commit()
            return int(cursor.rowcount or 0)

    def replace_payload_if_version(
        self,
        namespace,
        cache_key,
        payload,
        expected_updated_at,
    ):
        """
        Compare-and-swap a payload while preserving the provider TTL.

        If another analyzer refreshed the entry after it was read, rowcount is
        zero and the newer verdict remains authoritative.
        """
        with self._lock:
            cursor = self.db.execute(
                """
                UPDATE analyzer_cache_v1
                SET payload = ?
                WHERE namespace = ?
                  AND cache_key = ?
                  AND updated_at = ?
                """,
                (
                    payload,
                    namespace,
                    cache_key,
                    float(expected_updated_at),
                ),
            )

            self.db.commit()
            return int(cursor.rowcount or 0)

    def delete(
        self,
        namespace,
        cache_key,
    ):
        with self._lock:
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
        with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "stale": self.stale,
                "writes": self.writes,
            }

    def close(self):
        with self._lock:
            self.db.close()
