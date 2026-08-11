from app.dex.subscription_health import build_subscription_health


def test_connected():
    r = build_subscription_health(
        "CONNECTED", "publicnode", seconds_since_event=2
    )
    assert r["state"] == "CONNECTED"
    assert r["fresh"] is True


def test_stale():
    r = build_subscription_health(
        "CONNECTED", "publicnode",
        seconds_since_event=20,
        stale_seconds=10,
    )
    assert r["state"] == "STALE"
    assert r["stale"] is True


def test_degraded():
    r = build_subscription_health(
        "DEGRADED", "fallback"
    )
    assert r["state"] == "DEGRADED"
    assert r["degraded"] is True


def test_disconnected():
    r = build_subscription_health(
        "DISCONNECTED", "publicnode"
    )
    assert r["state"] == "DISCONNECTED"


def test_counts():
    r = build_subscription_health(
        "CONNECTED", "publicnode",
        seconds_since_event=1,
        reconnect_count=2,
        duplicate_count=3,
        dropped_count=4,
        rejected_count=5,
    )
    assert r["reconnect_count"] == 2
    assert r["duplicate_count"] == 3
    assert r["dropped_count"] == 4
    assert r["rejected_count"] == 5


def test_negative_counts_clamped():
    r = build_subscription_health(
        "CONNECTED", "publicnode",
        reconnect_count=-1,
        duplicate_count=-2,
    )
    assert r["reconnect_count"] == 0
    assert r["duplicate_count"] == 0


def test_unknown():
    assert build_subscription_health(
        "OTHER", "x"
    )["state"] == "UNKNOWN"


def test_authority_zero():
    r = build_subscription_health(
        "CONNECTED", "publicnode"
    )
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
