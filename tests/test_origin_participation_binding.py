import asyncio

from app.dex.native_ingestion import SWAP_TOPIC
from app.dex.runtime_actor_intelligence import (
    RuntimeActorIntelligence,
)
from app.dex.runtime_market_flow import (
    RuntimeMarketFlowStore,
)
from app.dex.transaction_origin import (
    TransactionOriginResolver,
)
from app.pipeline.market_context import (
    build_market_context,
)


PAIR = "0x00000000000000000000000000000000000000aa"
TOKEN = "0x0000000000000000000000000000000000000001"
QUOTE = "0x0000000000000000000000000000000000000002"
ROUTER1 = "0x0000000000000000000000000000000000000101"
ROUTER2 = "0x0000000000000000000000000000000000000202"
WALLET1 = "0x0000000000000000000000000000000000000aaa"
WALLET2 = "0x0000000000000000000000000000000000000bbb"


def word(value):
    return f"{value:064x}"


def topic_address(address):
    return "0x" + ("0" * 24) + address[2:]


def event(identity, tx_hash, sender, *, buy=True):
    if buy:
        amounts = (0, 10, 5, 0)
    else:
        amounts = (5, 0, 0, 10)

    return {
        "state": "NORMALIZED",
        "event_type": "SWAP",
        "event_identity": identity,
        "transaction_hash": tx_hash,
        "log_index": "0x1",
        "block_number": "0x10",
        "address": PAIR,
        "topics": [
            SWAP_TOPIC,
            topic_address(sender),
            topic_address(sender),
        ],
        "data": "0x" + "".join(
            word(value)
            for value in amounts
        ),
        "removed": False,
    }


def candidate():
    return {
        "pool": PAIR,
        "token": TOKEN,
        "quote_token": QUOTE,
        "liquidity": 50000.0,
        "volume_24h": 100000.0,
        "buys_24h": 20,
        "price_usd": 1.0,
    }


def configured_market():
    market = RuntimeMarketFlowStore(
        require_membership_confirmation=True
    )
    market.register_pair(PAIR, TOKEN, QUOTE)
    market.confirm_pair_membership(
        PAIR,
        TOKEN,
        QUOTE,
    )
    return market


def test_different_swap_senders_same_tx_origin_count_as_one_wallet():
    tx1 = "0x" + "1" * 64
    tx2 = "0x" + "2" * 64

    market = configured_market()
    actor = RuntimeActorIntelligence(
        resolver=TransactionOriginResolver(
            fetcher=lambda _: {
                "from": WALLET1,
            }
        )
    )

    first = event(
        "first",
        tx1,
        ROUTER1,
        buy=True,
    )
    second = event(
        "second",
        tx2,
        ROUTER2,
        buy=True,
    )

    for row in (first, second):
        observed = market.observe_event(row)
        asyncio.run(
            actor.observe_event(
                row,
                direction=observed["direction"],
            )
        )

    context = build_market_context(
        candidate(),
        runtime_feed=market,
    )

    flow = context["flow_intelligence"]
    quality_input = context["market_intelligence"]

    assert flow["unique_wallets"] == 1
    assert flow["largest_actor_share"] == 1.0
    assert flow["tx_count"] == 2
    assert (
        flow["participant_identity_source"]
        == "TRANSACTION_FROM_ONLY"
    )
    assert quality_input["buyers"] == 1
    assert (
        quality_input["participant_identity_source"]
        == "TRANSACTION_FROM_ONLY"
    )


def test_distinct_transaction_origins_count_as_distinct_wallets():
    tx1 = "0x" + "3" * 64
    tx2 = "0x" + "4" * 64

    origins = {
        tx1: WALLET1,
        tx2: WALLET2,
    }

    market = configured_market()
    actor = RuntimeActorIntelligence(
        resolver=TransactionOriginResolver(
            fetcher=lambda tx: {
                "from": origins[tx],
            }
        )
    )

    rows = (
        event("first", tx1, ROUTER1, buy=True),
        event("second", tx2, ROUTER1, buy=True),
    )

    for row in rows:
        observed = market.observe_event(row)
        asyncio.run(
            actor.observe_event(
                row,
                direction=observed["direction"],
            )
        )

    context = build_market_context(
        candidate(),
        runtime_feed=market,
    )

    flow = context["flow_intelligence"]
    market_input = context["market_intelligence"]

    assert flow["unique_wallets"] == 2
    assert flow["largest_actor_share"] == 0.5
    assert market_input["buyers"] == 2


def test_unresolved_origins_never_fall_back_to_swap_sender():
    tx1 = "0x" + "5" * 64

    market = configured_market()
    market.observe_event(
        event("first", tx1, ROUTER1, buy=True)
    )

    context = build_market_context(
        candidate(),
        runtime_feed=market,
    )

    flow = context["flow_intelligence"]
    market_input = context["market_intelligence"]

    assert "unique_wallets" not in flow
    assert "largest_actor_share" not in flow
    assert "buyers" not in market_input
    assert "sellers" not in market_input
    assert (
        flow["participant_identity_source"]
        == "TRANSACTION_FROM_ONLY"
    )
    assert flow["participant_identity_coverage"] == 0.0
