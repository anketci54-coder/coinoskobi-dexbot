from app.dex.wallet_evidence import normalize_wallet
from app.dex.entity_linking import same_entity_candidate, build_entity_link
from app.dex.known_wallet_registry import known_wallet_record
from app.dex.whale_flow import analyze_whale_flow
from app.dex.wallet_reputation import evaluate_wallet_reputation
from app.dex.wallet_readmodel import WalletReadModel


def test_same_address_different_chain_not_merged():
    a = normalize_wallet("bsc", "0xabc")["wallet_id"]
    b = normalize_wallet("eth", "0xabc")["wallet_id"]

    r = same_entity_candidate(a, b)

    assert r["candidate"] is False
    assert r["reason"] == "CROSS_CHAIN"
    assert r["auto_merge"] is False


def test_same_symbol_not_identity_evidence():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:TOKEN_SYMBOL_X",
        evidence_count=0,
        confidence=1.0,
    )
    assert r["state"] == "UNSUPPORTED"


def test_dust_attack_not_real_intent():
    r = analyze_whale_flow(
        1000,
        200,
        300,
        200,
        4,
        dust_ratio=0.9,
    )
    assert r["state"] == "NOISY"
    assert "DUST_NOISE" in r["tags"]


def test_single_whale_not_broad_participation():
    r = analyze_whale_flow(
        1000,
        900,
        700,
        100,
        1,
    )
    assert r["state"] == "CONCENTRATED"
    assert "SINGLE_WHALE_DOMINANCE" in r["tags"]


def test_fake_known_wallet_label_not_trusted():
    r = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "unknown_source",
        reliability=0.1,
    )
    assert r["known"] is True
    assert r["trusted"] is False
    assert r["trade_permission"] is False


def test_stale_known_wallet_not_fresh_signal():
    r = known_wallet_record(
        "bsc:0xabc",
        "SMART_MONEY",
        "source",
        reliability=1.0,
        freshness="STALE",
    )
    assert r["state"] == "STALE"


def test_cex_bridge_is_ambiguous_context():
    r = analyze_whale_flow(
        1000,
        300,
        500,
        200,
        3,
        cex_bridge=True,
    )
    assert "CEX_BRIDGE_EVIDENCE" in r["tags"]
    assert r["trade_signal"] is False


def test_conflicting_entity_evidence_unknown():
    r = build_entity_link(
        "bsc:0xabc",
        "entity:1",
        evidence_count=10,
        confidence=1.0,
        ambiguous=True,
    )
    assert r["state"] == "UNKNOWN"


def test_high_value_transfer_not_trade_signal():
    r = analyze_whale_flow(
        1000000,
        400000,
        700000,
        100000,
        3,
    )
    assert r["trade_signal"] is False


def test_hard_reputation_does_not_decay():
    old = evaluate_wallet_reputation(
        0, 0, 0,
        hard_evidence=True,
        soft_age=100,
    )
    assert old["state"] == "HARD_RISK_EVIDENCE"
    assert old["hard_evidence_decays"] is False


def test_readmodel_bounded_under_pressure():
    r = WalletReadModel(128)

    for i in range(10000):
        r.put(f"bsc:{i}", {"score": i})

    assert r.size == 128


def test_missing_readmodel_safe():
    r = WalletReadModel(128)
    assert r.get("bsc:missing")["state"] == "UNKNOWN"
