from app.pipeline.market_context import (
    build_market_context,
)


def test_candidate_liquidity_maps_to_context():
    result = build_market_context({
        "liquidity": 25_000,
    })

    assert (
        result["liquidity_usd"]
        == 25_000
    )

    assert (
        result["trade_size_usd"]
        is None
    )

    assert (
        result["price_impact_pct"]
        is None
    )

    assert (
        result["slippage_pct"]
        is None
    )


def test_real_execution_fields_are_preserved():
    result = build_market_context({
        "liquidity": 100_000,
        "trade_size_usd": 500,
        "price_impact_pct": 0.4,
        "slippage_pct": 0.6,
    })

    assert result == {
        "liquidity_usd": 100_000.0,
        "trade_size_usd": 500.0,
        "price_impact_pct": 0.4,
        "slippage_pct": 0.6,
    }


def test_missing_values_are_not_fabricated():
    result = build_market_context({})

    assert result == {
        "liquidity_usd": None,
        "trade_size_usd": None,
        "price_impact_pct": None,
        "slippage_pct": None,
    }


def test_invalid_negative_values_become_unknown():
    result = build_market_context({
        "liquidity": -1,
        "trade_size_usd": -1,
        "price_impact_pct": -1,
        "slippage_pct": -1,
    })

    assert all(
        value is None
        for value in result.values()
    )



def test_runtime_context_reads_candidate_snapshot_without_method_replacement():
    snapshot = {
        "market_intelligence": {},
        "flow_intelligence": {},
    }

    class RuntimeFeed:
        _events = {}

        def __init__(self):
            self.calls = []

        def snapshot(self, pair, candidate=None):
            self.calls.append((pair, candidate))
            return {
                "market_intelligence": dict(
                    snapshot["market_intelligence"]
                ),
                "flow_intelligence": dict(
                    snapshot["flow_intelligence"]
                ),
            }

    runtime = RuntimeFeed()
    original_snapshot_method = runtime.snapshot.__func__
    row = {
        "pool": "0x" + "1" * 40,
        "liquidity": 25_000,
    }

    result = build_market_context(
        row,
        runtime_feed=runtime,
    )

    assert runtime.calls == [
        (row["pool"], row)
    ]
    assert runtime.snapshot.__func__ is original_snapshot_method
    assert result["liquidity_usd"] == 25_000.0
    assert isinstance(
        result["runtime_market_flow"],
        dict,
    )
