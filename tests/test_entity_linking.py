from app.dex.entity_linking import (
    build_entity_link,
    same_entity_candidate,
)


def test_strong_link():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:1",
        evidence_count=4,
        confidence=0.95,
    )
    assert r["state"] == "STRONG_LINK"


def test_possible_link():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:1",
        evidence_count=2,
        confidence=0.70,
    )
    assert r["state"] == "POSSIBLE_LINK"


def test_weak_link():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:1",
        evidence_count=1,
        confidence=0.30,
    )
    assert r["state"] == "WEAK_LINK"


def test_ambiguous_unknown():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:1",
        evidence_count=10,
        confidence=1.0,
        ambiguous=True,
    )
    assert r["state"] == "UNKNOWN"


def test_stale_unknown():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:1",
        evidence_count=5,
        confidence=0.95,
        source_fresh=False,
    )
    assert r["state"] == "UNKNOWN"


def test_cross_chain_no_candidate():
    r = same_entity_candidate(
        "bsc:0xabc",
        "eth:0xabc",
    )
    assert r["candidate"] is False
    assert r["reason"] == "CROSS_CHAIN"
    assert r["auto_merge"] is False


def test_same_chain_same_address_candidate_but_no_auto_merge():
    r = same_entity_candidate(
        "bsc:0xabc",
        "bsc:0xabc",
    )
    assert r["candidate"] is True
    assert r["auto_merge"] is False


def test_different_address_no_candidate():
    r = same_entity_candidate(
        "bsc:0xabc",
        "bsc:0xdef",
    )
    assert r["candidate"] is False


def test_identity_not_proven():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:1",
        evidence_count=5,
        confidence=1.0,
    )
    assert r["identity_proof"] is False
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
