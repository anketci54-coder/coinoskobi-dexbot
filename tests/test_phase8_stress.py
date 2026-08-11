from app.dex.connection_health import connection_health
from app.dex.event_buffer import EventBuffer, buffer_health
from app.dex.event_integrity import validate_event_integrity
from app.dex.provider_resilience import (
    choose_provider,
    classify_provider_failure,
)
from app.dex.subscription_health import build_subscription_health
from app.dex.native_event_binding import bind_native_event_context


EVENT = {
    "state": "NORMALIZED",
    "event_type": "SWAP",
    "event_identity": "0xtx:0x1",
    "transaction_hash": "0xtx",
    "log_index": "0x1",
    "block_number": "0x10",
    "removed": False,
}


def test_disconnect_degraded():
    r = connection_health(False, None, reconnect_count=1)
    assert r["state"] == "DEGRADED"
    assert r["reconnect_allowed"] is True


def test_reconnect_limit_disconnects():
    r = connection_health(
        False, None,
        reconnect_count=5,
        max_reconnects=5,
    )
    assert r["state"] == "DISCONNECTED"
    assert r["reconnect_allowed"] is False


def test_duplicate_rejected():
    r = validate_event_integrity(
        {
            "transaction_hash": "0xtx",
            "log_index": "0x1",
            "block_number": "0x10",
            "removed": False,
        },
        seen={"0xtx:0x1"},
    )
    assert r["state"] == "DUPLICATE"


def test_removed_reorg_log():
    r = validate_event_integrity(
        {
            "transaction_hash": "0xtx",
            "log_index": "0x1",
            "block_number": "0x10",
            "removed": True,
        }
    )
    assert r["state"] == "REMOVED"


def test_burst_buffer_bounded():
    b = EventBuffer(100)

    for i in range(10000):
        b.push({"id": i})

    assert b.size == 100
    assert b.dropped == 9900
    assert buffer_health(b)["state"] == "FULL"


def test_provider_failover():
    r = choose_provider(
        {"name": "primary", "healthy": False},
        {"name": "fallback", "healthy": True},
    )
    assert r["state"] == "FALLBACK"


def test_provider_total_failure():
    r = choose_provider(
        {"name": "primary", "healthy": False},
        {"name": "fallback", "healthy": False},
    )
    assert r["state"] == "UNAVAILABLE"


def test_rate_limit_classification():
    assert classify_provider_failure(
        {"code": -32005, "message": "limit exceeded"}
    ) == "RATE_LIMIT"


def test_stale_subscription_blocks_binding():
    health = build_subscription_health(
        "CONNECTED",
        "publicnode",
        seconds_since_event=30,
        stale_seconds=10,
    )

    r = bind_native_event_context(
        EVENT,
        {"state": "ACCEPTED"},
        {"state": "HEALTHY"},
        health,
    )

    assert health["state"] == "STALE"
    assert r["native_context_ready"] is False


def test_full_buffer_blocks_binding():
    r = bind_native_event_context(
        EVENT,
        {"state": "ACCEPTED"},
        {"state": "FULL"},
        {
            "state": "CONNECTED",
            "provider_class": "publicnode",
            "fresh": True,
        },
    )
    assert r["native_context_ready"] is False


def test_clean_connected_path():
    r = bind_native_event_context(
        EVENT,
        {"state": "ACCEPTED"},
        {"state": "HEALTHY"},
        {
            "state": "CONNECTED",
            "provider_class": "publicnode",
            "fresh": True,
        },
    )
    assert r["native_context_ready"] is True


def test_authority_stays_zero():
    r = bind_native_event_context(
        EVENT,
        {"state": "ACCEPTED"},
        {"state": "HEALTHY"},
        {
            "state": "CONNECTED",
            "provider_class": "publicnode",
            "fresh": True,
        },
    )
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
