from app.dex.native_ingestion import (
    SWAP_TOPIC,
    SYNC_TOPIC,
    build_ingestion_contract,
    provider_capability,
)


PAIR = "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE"


def test_wss_contract():
    r = build_ingestion_contract(
        PAIR, "publicnode", "WSS"
    )
    assert r["state"] == "READY"
    assert r["topics"] == [SWAP_TOPIC, SYNC_TOPIC]
    assert r["bounded_read"] is True
    assert r["unbounded_getlogs_allowed"] is False


def test_http_contract():
    r = build_ingestion_contract(
        PAIR, "nodereal", "HTTP"
    )
    assert r["state"] == "READY"


def test_invalid_transport():
    assert build_ingestion_contract(
        PAIR, "x", "FTP"
    )["state"] == "UNSUPPORTED"


def test_wss_capability():
    r = provider_capability(
        "WSS", True, subscription_capable=True
    )
    assert r["state"] == "SUBSCRIPTION_READY"


def test_http_capability():
    r = provider_capability("HTTP", True)
    assert r["state"] == "BOUNDED_READ_ONLY"


def test_disconnected():
    assert provider_capability(
        "WSS", False
    )["state"] == "DISCONNECTED"


def test_authority_zero():
    r = build_ingestion_contract(
        PAIR, "publicnode", "WSS"
    )
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
