"""Canonical market-data boundary for runtime consumers."""

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
    """

    _shared_snapshot_client = ProviderStickySnapshotClient(
        primary=GeckoTerminalSnapshotClient(),
        fallback=DexScreenerSnapshotClient(),
    )

    def __init__(self, scanner=None, *, snapshot_client=None):
        self._scanner = scanner
        self._snapshot_client = snapshot_client or self._shared_snapshot_client
        if scanner is not None:
            binder = getattr(scanner, "bind_market_data_broker", None)
            if callable(binder):
                binder(self)

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
        snapshots = self._snapshot_client.fetch(pools)
        if persist_followups and snapshots:
            persist_registered_followup_snapshots(snapshots)
        return snapshots

    def __getattr__(self, name):
        if self._scanner is None:
            raise AttributeError(name)
        return getattr(self._scanner, name)
