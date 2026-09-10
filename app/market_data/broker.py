"""Canonical market-data boundary for runtime consumers."""


class MarketDataBroker:
    """Expose scanner market-data operations behind one stable boundary.

    Provider selection, cooldown and failover remain owned by the scanner.
    The broker deliberately adds no trading or decision authority; it only
    prevents pipeline consumers from depending on a concrete provider class.
    """

    def __init__(self, scanner):
        if scanner is None:
            raise ValueError("scanner required")
        self._scanner = scanner

    def pool_snapshots(self, pools, *, max_pools=30, persist_followups=False):
        return self._scanner.pool_snapshots(
            pools,
            max_pools=max_pools,
            persist_followups=persist_followups,
        )

    def __getattr__(self, name):
        return getattr(self._scanner, name)
