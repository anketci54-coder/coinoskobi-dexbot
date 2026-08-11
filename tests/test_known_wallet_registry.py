from app.dex.known_wallet_registry import (
    known_wallet_record,
    compare_label_with_behavior,
)


def test_high_confidence_source():
    r = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        0.95,
        provenance="manual_registry",
    )
    assert r["state"] == "HIGH_CONFIDENCE_SOURCE"
    assert r["known"] is True


def test_medium_source():
    r = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        0.70,
    )
    assert r["state"] == "MEDIUM_CONFIDENCE_SOURCE"


def test_low_source():
    r = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        0.20,
    )
    assert r["state"] == "LOW_CONFIDENCE_SOURCE"


def test_stale():
    r = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        1.0,
        freshness="STALE",
    )
    assert r["state"] == "STALE"


def test_known_not_trusted():
    r = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        1.0,
    )
    assert r["known"] is True
    assert r["trusted"] is False
    assert r["trade_permission"] is False
    assert r["identity_proof"] is False


def test_behavior_supports_label():
    record = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        0.95,
    )
    r = compare_label_with_behavior(
        record,
        ["ACCUMULATION_EVIDENCE"],
    )
    assert r["state"] == "SUPPORTED"


def test_behavior_contradicts_label():
    record = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        0.95,
    )
    r = compare_label_with_behavior(
        record,
        ["DISTRIBUTION_EVIDENCE"],
    )
    assert r["state"] == "CONTRADICTED"


def test_label_does_not_override_behavior():
    record = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source_a",
        0.95,
    )
    r = compare_label_with_behavior(record, [])
    assert r["label_overrides_behavior"] is False
    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
