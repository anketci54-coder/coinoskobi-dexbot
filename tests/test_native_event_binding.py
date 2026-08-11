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

INTEGRITY = {"state": "ACCEPTED"}
BUFFER = {"state": "HEALTHY"}
HEALTH = {
    "state": "CONNECTED",
    "provider_class": "publicnode",
    "fresh": True,
}


def test_ready():
    r = bind_native_event_context(
        EVENT, INTEGRITY, BUFFER, HEALTH
    )
    assert r["native_context_ready"] is True
    assert r["phase5_input_allowed"] is True
    assert r["phase7_input_allowed"] is True


def test_duplicate_not_ready():
    r = bind_native_event_context(
        EVENT,
        {"state": "DUPLICATE"},
        BUFFER,
        HEALTH,
    )
    assert r["native_context_ready"] is False


def test_stale_not_ready():
    h = dict(HEALTH)
    h["state"] = "STALE"
    h["fresh"] = False

    r = bind_native_event_context(
        EVENT, INTEGRITY, BUFFER, h
    )
    assert r["native_context_ready"] is False


def test_full_buffer_not_ready():
    r = bind_native_event_context(
        EVENT,
        INTEGRITY,
        {"state": "FULL"},
        HEALTH,
    )
    assert r["native_context_ready"] is False


def test_removed_preserved():
    e = dict(EVENT)
    e["removed"] = True

    r = bind_native_event_context(
        e,
        {"state": "REMOVED"},
        BUFFER,
        HEALTH,
    )
    assert r["removed"] is True
    assert r["native_context_ready"] is False


def test_unknown():
    r = bind_native_event_context({}, {}, {}, {})
    assert r["native_context_ready"] is False


def test_authority_zero():
    r = bind_native_event_context(
        EVENT, INTEGRITY, BUFFER, HEALTH
    )
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
