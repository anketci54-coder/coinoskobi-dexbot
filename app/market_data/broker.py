"""Canonical market-data boundary for runtime consumers."""

import sqlite3
from pathlib import Path

from app.scanner.followup_snapshot_cache import (
    persist_registered_followup_snapshots,
)
from app.universe.snapshot import (
    DexScreenerSnapshotClient,
    GeckoTerminalSnapshotClient,
    ProviderStickySnapshotClient,
)


class MarketDataBroker:
    """Single runtime boundary for scanner and universe market observations.

    Exact-pool provider selection, sticky source behavior and provider
    implementation details live behind this boundary. Runtime consumers
    never call a concrete market-data provider directly.

    Legacy pool-address callers are normalized here from the canonical
    market-data cache. Unknown addresses fail closed rather than guessing a
    DEX identity.
    """

    _shared_snapshot_client = ProviderStickySnapshotClient(
        primary=DexScreenerSnapshotClient(),
        fallback=GeckoTerminalSnapshotClient(),
    )
    _default_identity_db_path = Path("data/cache/cache.db")

    def __init__(
        self,
        scanner=None,
        *,
        snapshot_client=None,
        identity_db_path=None,
    ):
        self._scanner = scanner
        self._snapshot_client = snapshot_client or self._shared_snapshot_client
        self._identity_db_path = Path(
            identity_db_path or self._default_identity_db_path
        )
        if scanner is not None:
            binder = getattr(scanner, "bind_market_data_broker", None)
            if callable(binder):
                binder(self)

    @staticmethod
    def _canonical_pool(value):
        value = str(value or "").strip().lower()
        if value.startswith("bsc_"):
            value = value[4:]
        return value

    def _resolve_pool_identities(self, pools):
        normalized = []
        legacy = []

        for raw in pools or []:
            if isinstance(raw, dict):
                normalized.append(dict(raw))
                continue

            pool = self._canonical_pool(raw)
            if not pool:
                raise ValueError("pool identity mapping required")
            marker = {"pool": pool}
            normalized.append(marker)
            legacy.append(pool)

        if not legacy:
            return normalized

        if not self._identity_db_path.exists():
            raise ValueError("pool identity mapping required")

        placeholders = ",".join("?" for _ in sorted(set(legacy)))
        wanted = sorted(set(legacy))

        try:
            db = sqlite3.connect(self._identity_db_path, timeout=5)
            db.execute("PRAGMA busy_timeout=5000;")
            table = db.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table'
                  AND name='gecko_pool_cache'
                """
            ).fetchone()
            if table is None:
                db.close()
                raise ValueError("pool identity mapping required")

            rows = db.execute(
                """
                SELECT lower(pool) AS pool, dex
                FROM gecko_pool_cache
                WHERE lower(pool) IN (%s)
                """ % placeholders,
                wanted,
            ).fetchall()
            db.close()
        except sqlite3.Error as exc:
            raise ValueError("pool identity mapping required") from exc

        dex_by_pool = {
            self._canonical_pool(row[0]): str(row[1] or "").strip().lower()
            for row in rows
            if row[0] and row[1]
        }

        for item in normalized:
            if "dex" in item and item.get("dex"):
                item["pool"] = self._canonical_pool(item.get("pool"))
                item["dex"] = str(item["dex"]).strip().lower()
                continue

            pool = self._canonical_pool(item.get("pool"))
            dex = dex_by_pool.get(pool)
            if not dex:
                raise ValueError("pool identity mapping required")
            item["pool"] = pool
            item["dex"] = dex

        return normalized

    def pool_snapshots(self, pools, *, max_pools=30, persist_followups=False):
        return self.fetch(
            pools,
            max_pools=max_pools,
            persist_followups=persist_followups,
        )

    def fetch(self, pools, *, max_pools=30, persist_followups=False):
        """Fetch canonical exact-pool snapshots through the broker boundary."""
        if len(pools or []) > int(max_pools):
            raise ValueError("invalid bounded pool list")
        identities = self._resolve_pool_identities(pools)
        snapshots = self._snapshot_client.fetch(identities)
        if persist_followups and snapshots:
            persist_registered_followup_snapshots(snapshots)
        return snapshots

    def __getattr__(self, name):
        if self._scanner is None:
            raise AttributeError(name)
        return getattr(self._scanner, name)
