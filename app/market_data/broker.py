"""Canonical market-data boundary for runtime consumers."""

from app.universe.snapshot import ProviderStickySnapshotClient


class MarketDataBroker:
    """Single runtime boundary for scanner and universe market observations.

    Provider implementations remain private behind this boundary. Runtime
    consumers depend only on this broker for market-data access.
    """

    def __init__(self, scanner=None, *, snapshot_client=None):
        if scanner is None and snapshot_client is None:
            raise ValueError("scanner or snapshot_client required")
        self._scanner = scanner
        self._snapshot_client = snapshot_client or ProviderStickySnapshotClient()

    def pool_snapshots(self, pools, *, max_pools=30, persist_followups=False):
        if self._scanner is None:
            raise RuntimeError("scanner market-data source unavailable")
        return self._scanner.pool_snapshots(
            pools,
            max_pools=max_pools,
            persist_followups=persist_followups,
        )

    def fetch(self, pools):
        """Fetch canonical universe snapshots through the broker boundary."""
        return self._snapshot_client.fetch(pools)

    def __getattr__(self, name):
        if self._scanner is None:
            raise AttributeError(name)
        return getattr(self._scanner, name)
