"""Canonical read-only market-data facade.

The scanner owns provider failover and cooldown policy. This facade gives
pipeline consumers one stable entry point without exposing provider-specific
selection logic to those consumers.
"""


class MarketDataBroker:
    """Delegate bounded pool snapshots to the scanner provider broker."""

    def __init__(self, scanner):
        if scanner is None or not callable(
            getattr(scanner, "pool_snapshots", None)
        ):
            raise ValueError("scanner with pool_snapshots required")
        self.scanner = scanner

    def pool_snapshots(
        self,
        pools,
        *,
        max_pools=30,
        persist_followups=False,
    ):
        return self.scanner.pool_snapshots(
            pools,
            max_pools=max_pools,
            persist_followups=persist_followups,
        )
