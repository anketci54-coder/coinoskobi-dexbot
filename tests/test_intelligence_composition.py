from app.pipeline.intelligence_composition import (
    RuntimeIntelligenceComposition,
)


def test_missing_inputs_safe_unknown():
    c = RuntimeIntelligenceComposition()

    r = c.build(
        "0xtoken"
    )

    assert r[
        "market_regime"
    ]["market_regime"] == "UNKNOWN"

    assert r[
        "wallet_readmodel"
    ]["state"] == "UNKNOWN"

    assert r[
        "adversary_readmodel"
    ]["state"] == "UNKNOWN"

    assert r[
        "adversary_bridge"
    ]["candidate_action"] == "SAFE_DOWNGRADE"

    assert r[
        "can_upgrade_candidate"
    ] is False


def test_phase5_phase7_trending_bull():
    c = RuntimeIntelligenceComposition()

    r = c.build(
        "0xtoken",
        market_input={
            "volume_usd": 20000,
            "buy_volume_usd": 12000,
            "sell_volume_usd": 8000,
            "buyers": 20,
            "sellers": 20,
            "buys": 50,
            "sells": 50,
            "liquidity_usd": 50000,
        },
        flow_input={
            "buy_flow": 120,
            "sell_flow": 80,
            "prev_spread": 20,
            "prev_velocity": 5,
            "direction": "BULL",
            "price_direction": "UP",
            "unique_wallets": 10,
            "tx_count": 20,
            "largest_actor_share": 0.20,
            "freshness": "FRESH",
            "coverage": 1.0,
        },
    )

    assert r[
        "flow_confirmation"
    ]["confirmation"] == "CONFIRMED"

    assert r[
        "flow_divergence"
    ]["divergence_state"] == "STRENGTHENING"

    assert r[
        "flow_quality"
    ]["flow_quality"] == "MULTI_ACTOR"

    assert r[
        "market_regime"
    ]["market_regime"] == "TRENDING_BULL"


def test_phase9_phase10_readmodels_connected():
    c = RuntimeIntelligenceComposition()

    c.update_wallet(
        "bsc:0xabc",
        {
            "wallet_context_ready": True,
            "market_context_allowed": True,
            "wallet_id": "bsc:0xabc",
            "wallet_hard_risk": False,
        },
    )

    c.update_adversary(
        "actor:1",
        {
            "state": "LOW_RISK",
            "risk_score": 0.10,
            "hard_evidence": False,
            "evidence_tags": [],
        },
    )

    r = c.build(
        "0xtoken",
        wallet_id="bsc:0xabc",
        adversary_key="actor:1",
    )

    assert r[
        "wallet_readmodel"
    ]["state"] == "READY"

    assert r[
        "adversary_readmodel"
    ]["state"] == "READY"

    assert r[
        "adversary_bridge"
    ]["state"] == "CONTEXT_READY"

    assert r[
        "adversary_bridge"
    ]["candidate_action"] == "NO_ADVERSARY_BLOCK"


def test_hard_adversary_can_only_block():
    c = RuntimeIntelligenceComposition()

    c.update_wallet(
        "bsc:0xabc",
        {
            "wallet_context_ready": True,
            "market_context_allowed": True,
            "wallet_id": "bsc:0xabc",
            "wallet_hard_risk": False,
        },
    )

    c.update_adversary(
        "actor:hard",
        {
            "state": "HARD_ADVERSARY_EVIDENCE",
            "risk_score": 1.0,
            "hard_evidence": True,
            "evidence_tags": [
                "RUG_ASSOCIATION"
            ],
        },
    )

    r = c.build(
        "0xtoken",
        wallet_id="bsc:0xabc",
        adversary_key="actor:hard",
    )

    bridge = r[
        "adversary_bridge"
    ]

    assert bridge[
        "candidate_action"
    ] == "BLOCK_CANDIDATE"

    assert bridge[
        "can_upgrade_candidate"
    ] is False

    assert bridge[
        "trade_permission"
    ] is False


def test_runtime_connection_manifest():
    c = RuntimeIntelligenceComposition()

    r = c.build(
        "0xtoken"
    )

    expected = {
        "phase5_market",
        "phase7_flow_regime",
        "phase8_native_binding",
        "phase9_wallet_readmodel",
        "phase10_adversary_readmodel",
        "phase10_adversary_bridge",
    }

    assert set(
        r["runtime_connected"]
    ) == expected

    assert all(
        r["runtime_connected"].values()
    )


def test_authority_zero():
    c = RuntimeIntelligenceComposition()

    r = c.build(
        "0xtoken"
    )

    assert r[
        "context_only"
    ] is True

    assert r[
        "trade_permission"
    ] is False

    assert r[
        "decision_authority"
    ] is False

    assert r[
        "paper_authority"
    ] is False

    assert r[
        "live_authority"
    ] is False

    assert r[
        "wallet_authority"
    ] is False

    assert r[
        "execution_authority"
    ] is False
