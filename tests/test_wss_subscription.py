from app.dex.native_ingestion import SWAP_TOPIC, SYNC_TOPIC
from app.dex.wss_subscription import (
    subscribe_request,
    unsubscribe_request,
    normalize_wss_event,
)

PAIR = "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE"


def event(topic=SWAP_TOPIC):
    return {
        "method": "eth_subscription",
        "params": {
            "subscription": "0xsub",
            "result": {
                "topics": [topic],
                "transactionHash": "0xtx",
                "logIndex": "0x1",
                "blockNumber": "0x10",
                "removed": False,
            },
        },
    }


def test_subscribe():
    r = subscribe_request(PAIR)
    assert r["state"] == "READY"
    assert r["bounded"] is True
    assert r["request"]["method"] == "eth_subscribe"


def test_unsubscribe():
    assert unsubscribe_request("0xsub")["state"] == "READY"


def test_swap():
    r = normalize_wss_event(event())
    assert r["event_type"] == "SWAP"
    assert r["event_identity"] == "0xtx:0x1"


def test_sync():
    assert normalize_wss_event(
        event(SYNC_TOPIC)
    )["event_type"] == "SYNC"


def test_bad_topic():
    assert normalize_wss_event(
        event("0xdead")
    )["state"] == "REJECTED"


def test_invalid():
    assert subscribe_request(None)["state"] == "INVALID"
    assert unsubscribe_request(None)["state"] == "INVALID"


def test_authority_zero():
    r = normalize_wss_event(event())
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
