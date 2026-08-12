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
