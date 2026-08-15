from app.pipeline.command_center import (
    build_command_center_readmodel,
)


def test_command_center_composes_truth():
    result = build_command_center_readmodel(
        candidate={
            "token": "0xabc",
            "pool": "0xpool",
            "chain": "bsc",
            "liquidity": 50000,
        },
        pipeline_data={
            "strategy": {"decision": "WATCH"},
            "unified_score": {
                "score": 81,
                "confidence": 0.92,
            },
            "unified_decision": {"decision": "WATCH"},
            "risk_gate": {"hard_block": False},
            "paper": {
                "action": "WATCH",
                "reason": "WAIT_CONFIRMATION",
            },
            "analyzer_status": {
                "sellability": {
                    "status": "SELLABILITY_OK",
                }
            },
            "market_context": {
                "liquidity_usd": 50000,
            },
            "execution_cost": {
                "slippage_pct": 0.5,
                "mev_cost_pct": 0.1,
                "gas_cost_usd": 0.25,
                "net_expected_pnl_pct": 3.2,
            },
        },
        paper_outcome={
            "outcome_class": "WIN",
            "roi_pct": 4.1,
        },
    )

    assert result["candidate"]["token"] == "0xabc"
    assert result["decision"]["score"] == 81.0
    assert result["decision"]["confidence"] == 0.92
    assert result["decision"]["hard_block"] is False
    assert result["paper"]["latest_outcome"] == "WIN"
    assert result["execution"]["gas_cost_usd"] == 0.25

    assert result["bounded"] is True
    assert result["read_only"] is True
    assert result["hot_path_wait"] is False
    assert result["provider_call"] is False
    assert result["ai_inference"] is False

    assert result["trade_authority"] is False
    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
    assert result["hardblock_override_authority"] is False


def test_command_center_preserves_hard_block():
    result = build_command_center_readmodel(
        candidate={"token": "0xbad"},
        pipeline_data={
            "unified_decision": {"decision": "REJECT"},
            "risk_gate": {"hard_block": True},
            "analyzer_status": {
                "sellability": {
                    "status": "SELLABILITY_FAIL",
                }
            },
        },
    )

    assert result["decision"]["hard_block"] is True
    assert "HARD_RISK_BLOCK" in result["decision"]["blockers"]
    assert "SELLABILITY_BLOCK" in result["decision"]["blockers"]
    assert result["decision"]["approval_required"] is True

    assert result["trade_authority"] is False
    assert result["live_authority"] is False
    assert result["execution_authority"] is False
    assert result["hardblock_override_authority"] is False
