from app.market_data.broker import MarketDataBroker


class _Scanner:
    def __init__(self):
        self.calls = []

    def pool_snapshots(self, pools, *, max_pools=30, persist_followups=False):
        self.calls.append((list(pools), max_pools, persist_followups))
        return [{"pool": "0xpool", "provider": "dexscreener"}]

    def scan(self):
        return ["delegated"]


def test_broker_delegates_bounded_pool_snapshots():
    scanner = _Scanner()
    broker = MarketDataBroker(scanner)

    result = broker.pool_snapshots(
        ["0xpool"],
        max_pools=1,
        persist_followups=False,
    )

    assert result[0]["provider"] == "dexscreener"
    assert scanner.calls == [(["0xpool"], 1, False)]


def test_broker_keeps_scanner_operations_compatible():
    scanner = _Scanner()
    broker = MarketDataBroker(scanner)

    assert broker.scan() == ["delegated"]


def test_broker_requires_scanner():
    try:
        MarketDataBroker(None)
    except ValueError as exc:
        assert str(exc) == "scanner required"
    else:
        raise AssertionError("expected ValueError")
