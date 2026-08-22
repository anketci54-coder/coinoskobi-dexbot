from app.dex.native_ingestion import SWAP_TOPIC
from app.dex.runtime_market_flow import (
    RuntimeMarketFlowStore,
    decode_v2_swap,
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

SENDER = (
    "0x0000000000000000000000000000000000000abc"
)


def word(value):
    return f"{value:064x}"


def topic_address(address):
    return (
        "0x"
        + ("0" * 24)
        + address[2:]
    )


def swap_event(
    identity,
    *,
    amount0_in=0,
    amount1_in=0,
    amount0_out=0,
    amount1_out=0,
):
    return {
        "state": "NORMALIZED",
        "event_type": "SWAP",
        "event_identity": identity,
        "transaction_hash": (
            identity.split(":")[0]
        ),
        "log_index": "0x1",
        "block_number": "0x10",
        "address": PAIR,
        "topics": [
            SWAP_TOPIC,
            topic_address(
                SENDER
            ),
            topic_address(
                SENDER
            ),
        ],
        "data": (
            "0x"
            + word(amount0_in)
            + word(amount1_in)
            + word(amount0_out)
            + word(amount1_out)
        ),
        "removed": False,
    }


def test_decode_v2_swap_preserves_real_amounts():
    event = swap_event(
        "0xaaa:0x1",
        amount1_in=10,
        amount0_out=5,
    )

    r = decode_v2_swap(
        event
    )

    assert r["state"] == "DECODED"
    assert r["amount1_in"] == 10
    assert r["amount0_out"] == 5
    assert r["sender"] == SENDER


def test_registered_target_direction_is_real():
    store = RuntimeMarketFlowStore()

    r = store.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    assert r[
        "token_is_0"
    ] is True

    buy = store.observe_event(
        swap_event(
            "0xbuy:0x1",
            amount1_in=10,
            amount0_out=5,
        )
    )

    sell = store.observe_event(
        swap_event(
            "0xsell:0x2",
            amount0_in=5,
            amount1_out=10,
        )
    )

    assert buy["direction"] == "BULL"
    assert sell["direction"] == "BEAR"


def test_snapshot_combines_scanner_and_wss():
    store = RuntimeMarketFlowStore()

    store.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    store.observe_event(
        swap_event(
            "0xbuy:0x1",
            amount1_in=10,
            amount0_out=5,
        )
    )

    result = store.snapshot(
        PAIR,
        candidate={
            "pool": PAIR,
            "liquidity": 50000,
            "volume_24h": 125000,
            "buys_24h": 20,
            "price_usd": 1.0,
        },
    )

    market = result[
        "market_intelligence"
    ]

    flow = result[
        "flow_intelligence"
    ]

    assert result["state"] == "READY"
    assert market[
        "liquidity_usd"
    ] == 50000

    assert market[
        "volume_usd"
    ] == 125000

    assert market["buys"] == 1
    assert market["sells"] == 0
    assert market["buyers"] == 1

    assert flow[
        "evidence_ready"
    ] is True

    assert flow["buy_flow"] == 1
    assert flow["sell_flow"] == 0
    assert flow["direction"] == "BULL"
    assert flow["tx_count"] == 1
    assert flow["source"] == "NATIVE_WSS"


def test_retraction_removes_native_observation():
    store = RuntimeMarketFlowStore()

    store.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    event = swap_event(
        "0xbuy:0x1",
        amount1_in=10,
        amount0_out=5,
    )

    store.observe_event(
        event
    )

    assert store.event_count == 1

    retract = dict(event)

    retract[
        "retracts_event_identity"
    ] = event[
        "event_identity"
    ]

    r = store.observe_retraction(
        retract
    )

    assert r["state"] == "RETRACTED"
    assert store.event_count == 0


def test_store_is_strictly_bounded():
    store = RuntimeMarketFlowStore(
        max_pairs=2,
        max_events_per_pair=16,
    )

    store.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    for i in range(10000):
        store.observe_event(
            swap_event(
                f"0x{i:064x}:0x1",
                amount1_in=10,
                amount0_out=5,
            )
        )

    assert store.event_count == 16

    status = store.status()

    assert status["bounded"] is True
    assert status[
        "dropped_events"
    ] > 0

    assert status[
        "decision_authority"
    ] is False

    assert status[
        "execution_authority"
    ] is False


def test_unknown_pair_never_invents_flow():
    store = RuntimeMarketFlowStore()

    event = swap_event(
        "0xaaa:0x1",
        amount1_in=10,
        amount0_out=5,
    )

    r = store.observe_event(
        event
    )

    assert r["state"] == "IGNORED"

    snapshot = store.snapshot(
        PAIR,
        candidate={},
    )

    assert snapshot["state"] == "UNKNOWN"

    assert snapshot[
        "flow_intelligence"
    ][
        "evidence_ready"
    ] is False

def test_direction_requires_confirmed_pair_membership():
    store = RuntimeMarketFlowStore(
        require_membership_confirmation=True
    )

    registered = store.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    assert registered["state"] == "REGISTERED"

    event = swap_event(
        "0xconfirm:0x1",
        amount0_in=0,
        amount1_in=10,
        amount0_out=5,
        amount1_out=0,
    )

    first = store.observe_event(event)
    assert first["direction"] == "UNKNOWN"

    mismatch = store.confirm_pair_membership(
        PAIR,
        TOKEN,
        "0x0000000000000000000000000000000000000999",
    )

    assert mismatch["state"] == "MISMATCH"

    verified = store.confirm_pair_membership(
        PAIR,
        TOKEN,
        QUOTE,
    )

    assert verified["state"] == "VERIFIED"

    event2 = swap_event(
        "0xconfirm2:0x2",
        amount0_in=0,
        amount1_in=10,
        amount0_out=5,
        amount1_out=0,
    )

    second = store.observe_event(event2)

    assert second["direction"] in {
        "BULL",
        "BEAR",
    }

def test_market_evidence_wait_requires_real_buy_and_sell_actors():
    store = RuntimeMarketFlowStore(
        require_membership_confirmation=True
    )

    store.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    store.confirm_pair_membership(
        PAIR,
        TOKEN,
        QUOTE,
    )

    store.observe_event(
        swap_event(
            "0xwarmbuy:0x1",
            amount1_in=10,
            amount0_out=5,
        )
    )

    partial = (
        store.wait_for_market_evidence(
            [PAIR],
            timeout=0.0,
        )
    )

    assert partial["state"] == "TIMEOUT"
    assert partial["ready"] == 0
    assert partial["pending"] == 1

    store.observe_event(
        swap_event(
            "0xwarmsell:0x2",
            amount0_in=5,
            amount1_out=10,
        )
    )

    ready = (
        store.wait_for_market_evidence(
            [PAIR],
            timeout=0.0,
        )
    )

    assert ready["state"] == "READY"
    assert ready["requested"] == 1
    assert ready["ready"] == 1
    assert ready["pending"] == 0
    assert ready["decision_authority"] is False
    assert ready["execution_authority"] is False
