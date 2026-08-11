from app.dex.provider_resilience import (
    classify_provider_failure,
    choose_provider,
    failover_allowed,
)


def test_primary():
    r = choose_provider(
        {"name": "p1", "healthy": True},
        {"name": "p2", "healthy": True},
    )
    assert r["state"] == "PRIMARY"
    assert r["provider"] == "p1"


def test_fallback():
    r = choose_provider(
        {"name": "p1", "healthy": False},
        {"name": "p2", "healthy": True},
    )
    assert r["state"] == "FALLBACK"
    assert r["provider"] == "p2"


def test_unavailable():
    r = choose_provider(
        {"name": "p1", "healthy": False},
        {"name": "p2", "healthy": False},
    )
    assert r["state"] == "UNAVAILABLE"


def test_rate_limit():
    assert classify_provider_failure(
        {"code": -32005, "message": "limit exceeded"}
    ) == "RATE_LIMIT"


def test_timeout():
    assert classify_provider_failure(
        "subscription timeout"
    ) == "TIMEOUT"


def test_connection():
    assert classify_provider_failure(
        "connection closed"
    ) == "CONNECTION"


def test_failover_bounded():
    r = failover_allowed(
        attempts=0,
        max_failovers=1,
    )
    assert r["allowed"] is True
    assert r["bounded"] is True


def test_failover_limit():
    r = failover_allowed(
        attempts=1,
        max_failovers=1,
    )
    assert r["allowed"] is False


def test_no_fallback():
    assert failover_allowed(
        0,
        fallback_available=False,
    )["allowed"] is False


def test_safety():
    r = choose_provider(
        {"name": "p1", "healthy": True}
    )
    assert r["paid_provider_required"] is False
    assert r["secret_logging_allowed"] is False
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
