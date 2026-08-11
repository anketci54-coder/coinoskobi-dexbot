from app.dex.event_integrity import (
    event_identity,
    validate_event_integrity,
)


def event(
    tx="0xtx",
    idx="0x2",
    block="0x10",
    removed=False,
):
    return {
        "transaction_hash": tx,
        "log_index": idx,
        "block_number": block,
        "removed": removed,
    }


def test_identity():
    assert event_identity(event()) == "0xtx:0x2"


def test_missing_identity():
    e = event()
    e["transaction_hash"] = None
    r = validate_event_integrity(e)
    assert r["state"] == "REJECTED"


def test_duplicate():
    r = validate_event_integrity(
        event(),
        seen={"0xtx:0x2"},
    )
    assert r["state"] == "DUPLICATE"


def test_removed():
    r = validate_event_integrity(
        event(removed=True)
    )
    assert r["state"] == "REMOVED"


def test_accepted():
    r = validate_event_integrity(
        event(),
        last_block="0xf",
        last_log_index="0x20",
    )
    assert r["state"] == "ACCEPTED"


def test_older_block():
    r = validate_event_integrity(
        event(block="0x10"),
        last_block="0x11",
        last_log_index="0x1",
    )
    assert r["state"] == "OUT_OF_ORDER"


def test_lower_log_index_same_block():
    r = validate_event_integrity(
        event(idx="0x2", block="0x10"),
        last_block="0x10",
        last_log_index="0x3",
    )
    assert r["state"] == "OUT_OF_ORDER"


def test_higher_log_index_same_block():
    r = validate_event_integrity(
        event(idx="0x4", block="0x10"),
        last_block="0x10",
        last_log_index="0x3",
    )
    assert r["state"] == "ACCEPTED"


def test_invalid_order_field():
    r = validate_event_integrity(
        event(block="bad")
    )
    assert r["state"] == "REJECTED"


def test_authority_zero():
    r = validate_event_integrity(event())
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
