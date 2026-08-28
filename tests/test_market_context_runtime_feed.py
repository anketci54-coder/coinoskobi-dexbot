from app.dex.native_ingestion import SWAP_TOPIC
from app.dex.runtime_market_flow import (
    RuntimeMarketFlowStore,
)
from app.pipeline.market_context import (
    build_market_context,
)


TOKEN = (
    "0x0000000000000000000000000000000000000001"
)

QUOTE = (
    "0x0000000000000000000000000000000000000002"
)

PAIR = (
    "0x00000000000000000000000000000000000000aa"
)


def word(value):
    return f"{value:064x}"


def test_build_market_context_uses_operational_feed():
    feed = RuntimeMarketFlowStore()

    feed.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    feed.observe_event({
        "event_type": "SWAP",
        "event_identity": "0xaaa:0x1",
        "transaction_hash": "0xaaa",
        "log_index": "0x1",
        "block_number": "0x10",
        "address": PAIR,
        "topics": [
            SWAP_TOPIC
        ],
        "data": (
            "0x"
            + word(0)
            + word(10)
            + word(5)
            + word(0)
        ),
    })

    row = {
        "pool": PAIR,
        "token": TOKEN,
        "liquidity": 100000,
        "volume_24h": 250000,
        "buys_24h": 30,
        "price_usd": 2.0,
    }

    result = build_market_context(
        row,
        runtime_feed=feed,
    )

    assert (
        result[
            "market_intelligence"
        ][
            "volume_usd"
        ]
        == 250000
    )

    assert (
        result[
            "flow_intelligence"
        ][
            "buy_flow"
        ]
        == 1
    )

    assert (
        result[
            "runtime_market_flow"
        ][
            "synthetic"
        ]
        is False
    )


def test_candidate_native_snapshot_is_reused_once_for_same_evaluation():
    class MutableFeed:
        def __init__(self):
            self._events = {}
            self.calls = 0
            self.acceleration = 0.25

        def snapshot(self, pair, candidate=None):
            self.calls += 1
            return {
                "state": "READY",
                "market_intelligence": {
                    "evidence_ready": True,
                },
                "flow_intelligence": {
                    "evidence_ready": True,
                    "buy_flow": 7,
                    "sell_flow": 3,
                    "prev_spread": 1,
                    "prev_velocity": 0,
                    "freshness": "FRESH",
                    "coverage": 1.0,
                    "flow_acceleration": self.acceleration,
                },
                "synthetic": False,
            }

    feed = MutableFeed()
    row = {
        "pool": PAIR,
        "token": TOKEN,
        "liquidity": 1000,
        "price_usd": 1.0,
    }

    first = build_market_context(
        row,
        runtime_feed=feed,
    )

    assert feed.calls == 1
    assert (
        first["flow_intelligence"][
            "flow_acceleration"
        ]
        == 0.25
    )

    # Native evidence changes while the same candidate evaluation is
    # still running. The immediate audit/shadow read must remain atomic.
    feed.acceleration = -0.50

    frozen = feed.snapshot(
        PAIR,
        candidate=row,
    )

    assert feed.calls == 1
    assert (
        frozen["flow_intelligence"][
            "flow_acceleration"
        ]
        == 0.25
    )

    # The bridge is one-shot. Later lifecycle/scan reads remain live.
    live = feed.snapshot(
        PAIR,
        candidate=row,
    )

    assert feed.calls == 2
    assert (
        live["flow_intelligence"][
            "flow_acceleration"
        ]
        == -0.50
    )


def test_no_feed_preserves_old_contract():
    result = build_market_context({
        "liquidity": 1000,
    })

    assert result == {
        "liquidity_usd": 1000.0,
        "trade_size_usd": None,
        "price_impact_pct": None,
        "slippage_pct": None,
    }
