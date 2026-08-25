import asyncio

from app.dex.native_ingestion import SWAP_TOPIC
from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.dex.runtime_market_flow import RuntimeMarketFlowStore
from app.dex.transaction_origin import TransactionOriginResolver
from app.pipeline.intelligence_composition import RuntimeIntelligenceComposition
from app.pipeline.market_context import build_market_context
from app.strategy.mathematical_trade_plan import build_trade_plan


PAIR = "0x00000000000000000000000000000000000000aa"
TOKEN = "0x0000000000000000000000000000000000000001"
QUOTE = "0x0000000000000000000000000000000000000002"
ROUTER1 = "0x0000000000000000000000000000000000000101"
ROUTER2 = "0x0000000000000000000000000000000000000202"
WALLET = "0x0000000000000000000000000000000000000aaa"


def word(value):
    return f"{value:064x}"


def topic(address):
    return "0x" + ("0" * 24) + address[2:]


def buy_event(identity, tx_hash, sender):
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
            topic(sender),
            topic(sender),
        ],
        "data": "0x" + word(0) + word(10) + word(5) + word(0),
        "removed": False,
    }


def test_same_tx_origin_blocks_concentrated_entry_despite_router_senders():
    market = RuntimeMarketFlowStore(
        require_membership_confirmation=True
    )
    market.register_pair(PAIR, TOKEN, QUOTE)
    market.confirm_pair_membership(PAIR, TOKEN, QUOTE)

    actor = RuntimeActorIntelligence(
        resolver=TransactionOriginResolver(
            fetcher=lambda _: {"from": WALLET}
        )
    )

    rows = (
        buy_event("a", "0x" + "1" * 64, ROUTER1),
        buy_event("b", "0x" + "2" * 64, ROUTER2),
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
        {
            "pool": PAIR,
            "token": TOKEN,
            "quote_token": QUOTE,
            "liquidity": 50000.0,
            "volume_24h": 100000.0,
            "buys_24h": 20,
            "price_usd": 1.05,
        },
        runtime_feed=market,
    )

    intelligence = RuntimeIntelligenceComposition().build(
        TOKEN,
        market_input=context["market_intelligence"],
        flow_input=context["flow_intelligence"],
    )

    assert (
        intelligence["market_quality"]["participation_state"]
        == "CONCENTRATED"
    )
    assert (
        intelligence["market_quality"]["suspicious_volume"]
        is True
    )

    plan = build_trade_plan(
        entry_price=1.05,
        available_capital_usdt=10000.0,
        price_series=[1.00, 1.02, 1.05],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data={
            "buy_tax": 0.0,
            "sell_tax": 0.0,
            "buy_gas": 0.0,
            "sell_gas": 0.0,
        },
        exit_evidence={
            "route_friction_fraction": 0.0,
            "gas_price_wei": 0.0,
            "wbnb_usd_estimate": 600.0,
        },
        market_context={
            "market_intelligence": context["market_intelligence"],
            "flow_intelligence": context["flow_intelligence"],
            "runtime_intelligence": intelligence,
        },
    )

    blockers = set(plan["blockers"])

    assert "PARTICIPATION_CONCENTRATED" in blockers
    assert "SUSPICIOUS_VOLUME" in blockers
    assert plan["paper_eligible"] is False
