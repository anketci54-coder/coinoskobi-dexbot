from app.dex.connection_health import (
    reconnect_delay,
    connection_health,
)


def test_connected():
    assert connection_health(
        True, 2
    )["state"] == "CONNECTED"


def test_stale():
    r = connection_health(True, 20, stale_seconds=10)
    assert r["state"] == "STALE"
    assert r["stale"] is True


def test_degraded():
    r = connection_health(
        False, None, reconnect_count=2
    )
    assert r["state"] == "DEGRADED"
    assert r["reconnect_allowed"] is True


def test_reconnect_limit():
    r = connection_health(
        False, None,
        reconnect_count=5,
        max_reconnects=5,
    )
    assert r["state"] == "DISCONNECTED"
    assert r["reconnect_allowed"] is False


def test_backoff():
    assert reconnect_delay(0) == 1
    assert reconnect_delay(1) == 2
    assert reconnect_delay(2) == 4


def test_backoff_bounded():
    assert reconnect_delay(
        20, maximum=30
    ) == 30


def test_authority_zero():
    r = connection_health(False, None)
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
