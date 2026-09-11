from app.market_data.broker import MarketDataBroker


class _Scanner:
    def __init__(self):
        self.broker = None

    def bind_market_data_broker(self, broker):
        self.broker = broker

    def scan(self):
        return ["delegated"]


class _SnapshotClient:
    def __init__(self):
        self.calls = []

    def fetch(self, pools):
        self.calls.append(list(pools))
        return [{"pool": "0xpool", "provider": "geckoterminal"}]


def test_broker_owns_bounded_pool_snapshots():
    scanner = _Scanner()
    snapshot_client = _SnapshotClient()
    broker = MarketDataBroker(scanner, snapshot_client=snapshot_client)

    result = broker.pool_snapshots(
        ["0xpool"],
        max_pools=1,
        persist_followups=False,
    )

    assert result[0]["provider"] == "geckoterminal"
    assert snapshot_client.calls == [["0xpool"]]
    assert scanner.broker is broker


def test_broker_keeps_scanner_operations_compatible():
    scanner = _Scanner()
    broker = MarketDataBroker(scanner, snapshot_client=_SnapshotClient())

    assert broker.scan() == ["delegated"]


def test_broker_requires_scanner_or_snapshot_client():
    try:
        MarketDataBroker(None)
    except ValueError as exc:
        assert str(exc) == "scanner or snapshot_client required"
    else:
        raise AssertionError("expected ValueError")
