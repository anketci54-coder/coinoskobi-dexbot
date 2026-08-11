from app.dex.mev_sandwich import (
    evaluate_sandwich_evidence,
    classify_mev_context,
)
from app.dex.scam_rug_patterns import evaluate_scam_rug_patterns
from app.dex.wash_sybil_intelligence import evaluate_wash_sybil
from app.dex.sniper_pumpdump import evaluate_sniper_pumpdump
from app.dex.adversary_reputation import evaluate_adversary_reputation
from app.dex.adversary_market_bridge import bind_adversary_market_context
from app.dex.adversary_readmodel import (
    AdversaryReadModel,
    hot_path_contract,
)
from app.dex.whale_flow import analyze_whale_flow


WALLET_READY = {
    "wallet_context_ready": True,
    "market_context_allowed": True,
    "wallet_id": "bsc:0xabc",
    "wallet_hard_risk": False,
}


def test_normal_arbitrage_not_sandwich():
    raw = evaluate_sandwich_evidence(
        same_block=True,
        frontrun_before_victim=True,
        backrun_after_victim=True,
        victim_price_impact=0.0,
        repeated_pattern_count=0,
    )

    assert raw["state"] == "MEV_LIKE_ORDERING"

    ctx = classify_mev_context(
        raw["state"],
        arbitrage_like=True,
    )

    assert ctx["state"] == "NORMAL_ARBITRAGE_POSSIBLE"
    assert ctx["normal_arbitrage_is_sandwich"] is False


def test_single_suspicious_ordering_not_mev_proof():
    r = evaluate_sandwich_evidence(
        True, True, True,
        victim_price_impact=0.0,
        repeated_pattern_count=0,
    )

    assert r["state"] == "MEV_LIKE_ORDERING"
    assert r["single_event_is_proof"] is False


def test_single_whale_not_attacker():
    r = analyze_whale_flow(
        total_value=1000,
        largest_wallet_value=900,
        whale_inflow=700,
        whale_outflow=100,
        unique_whales=1,
    )

    assert r["state"] == "CONCENTRATED"
    assert r["trade_signal"] is False


def test_same_funder_not_same_actor():
    r = evaluate_scam_rug_patterns(
        suspicious_funder_links=5,
        confidence=1.0,
    )

    assert r["state"] == "SUSPICIOUS_ASSOCIATION"
    assert r["same_funder_is_same_actor"] is False
    assert r["identity_proof"] is False


def test_benign_sniper_not_malicious():
    r = evaluate_sniper_pumpdump(
        early_buy_count=3,
        coordinated_early_buy_score=0.1,
        accumulation_concentration=0.2,
        distribution_concentration=0.1,
        synchronized_dump_score=0.0,
        repeat_pumpdump_count=0,
    )

    assert r["state"] == "SNIPER_ACTIVITY"
    assert r["sniper_is_malicious_proof"] is False


def test_coordinated_pumpdump_detected():
    r = evaluate_sniper_pumpdump(
        early_buy_count=20,
        coordinated_early_buy_score=0.95,
        accumulation_concentration=0.9,
        distribution_concentration=0.95,
        synchronized_dump_score=0.95,
        repeat_pumpdump_count=3,
    )

    assert r["state"] == "STRONG_PUMPDUMP_EVIDENCE"


def test_fake_multi_actor_vs_real_independent():
    fake = evaluate_wash_sybil(
        wallet_count=30,
        repeated_counterparty_ratio=0.9,
        circular_flow_ratio=0.9,
        coordination_score=0.9,
        independent_wallet_ratio=0.1,
    )

    real = evaluate_wash_sybil(
        wallet_count=30,
        repeated_counterparty_ratio=0.1,
        circular_flow_ratio=0.1,
        coordination_score=0.1,
        independent_wallet_ratio=0.9,
    )

    assert fake["state"] == "STRONG_WASH_SYBIL_EVIDENCE"
    assert real["state"] == "INDEPENDENT_PARTICIPATION"


def test_stale_scam_evidence_unknown():
    r = evaluate_scam_rug_patterns(
        repeat_rug_count=10,
        liquidity_removal_count=10,
        honeypot_associations=10,
        confidence=1.0,
        freshness="STALE",
    )

    assert r["state"] == "UNKNOWN"


def test_conflicting_soft_evidence_safe_downgrade():
    rep = evaluate_adversary_reputation(
        mev_state="ELEVATED_MEV_RISK",
        scam_state="SCAM_RUG_CANDIDATE",
        conflicting_evidence=True,
    )

    assert rep["state"] == "UNRESOLVED_CONFLICT"

    bridge = bind_adversary_market_context(
        WALLET_READY,
        rep,
    )

    assert bridge["candidate_action"] == "SAFE_DOWNGRADE"
    assert bridge["can_upgrade_candidate"] is False


def test_hard_evidence_blocks_and_does_not_decay():
    fresh = evaluate_adversary_reputation(
        scam_state="STRONG_SCAM_RUG_EVIDENCE",
        hard_evidence=True,
        soft_age=0,
    )

    old = evaluate_adversary_reputation(
        scam_state="STRONG_SCAM_RUG_EVIDENCE",
        hard_evidence=True,
        soft_age=100,
    )

    assert fresh["risk_score"] == old["risk_score"]
    assert old["hard_evidence_decays"] is False

    bridge = bind_adversary_market_context(
        WALLET_READY,
        old,
    )

    assert bridge["candidate_action"] == "BLOCK_CANDIDATE"
    assert bridge["hard_safety_override_allowed"] is False


def test_adversary_readmodel_bounded_under_pressure():
    r = AdversaryReadModel(128)

    for i in range(10000):
        r.put(
            f"bsc:{i}",
            {
                "adversary_risk_bucket": "LOW_RISK",
                "soft_evidence_score": 0.1,
            },
        )

    assert r.size == 128
    assert r.get("bsc:9999")["state"] == "READY"
    assert r.get("bsc:0")["state"] == "UNKNOWN"


def test_hot_path_forbidden_operations_locked():
    c = hot_path_contract()

    assert c["deep_transaction_trace"] is False
    assert c["graph_expansion"] is False
    assert c["raw_event_join"] is False
    assert c["heavy_actor_aggregation"] is False
    assert c["ai_inference"] is False
    assert c["external_fetch"] is False
    assert c["provider_call"] is False

    assert c["decision_authority"] is False
    assert c["paper_authority"] is False
    assert c["live_authority"] is False
    assert c["wallet_authority"] is False
    assert c["execution_authority"] is False
