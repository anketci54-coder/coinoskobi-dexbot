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


def test_command_center_projects_complete_simulation_drift():
    result = build_command_center_readmodel(
        candidate={"token": "0xdrift"},
        pipeline_data={
            "simulation_drift": {
                "comparable_evidence_count": 6,
                "comparison_complete": True,
                "observed_evidence_count": 8,
                "observed_evidence_complete": True,
                "missing_observed_fields": [],
                "simulation_drift": {
                    "liquidity": {
                        "paper_usd": 50000.0,
                        "observed_usd": 48000.0,
                        "delta_usd": -2000.0,
                    },
                    "sellability": {
                        "paper": "SELLABILITY_OK",
                        "observed": "SELLABILITY_OK",
                        "changed": False,
                    },
                    "drift": {
                        "slippage_pct": {
                            "paper": 0.5,
                            "observed": 0.7,
                            "delta": 0.2,
                        },
                    },
                },
            },
        },
    )

    drift = result["simulation_drift"]

    assert drift["state"] == "OBSERVED"
    assert drift["comparison_complete"] is True
    assert drift["comparable_evidence_count"] == 6
    assert drift["liquidity"]["delta_usd"] == -2000.0
    assert drift["sellability"]["changed"] is False
    assert drift["drift"]["slippage_pct"]["delta"] == 0.2

    assert drift["observation_only"] is True
    assert drift["decision_authority"] is False
    assert drift["execution_authority"] is False
    assert drift["hardblock_override_authority"] is False


def test_command_center_drift_missing_evidence_is_not_bad_drift():
    result = build_command_center_readmodel(
        candidate={"token": "0xunknown"},
        pipeline_data={
            "simulation_drift": {
                "comparable_evidence_count": 2,
                "comparison_complete": False,
                "observed_evidence_count": 2,
                "observed_evidence_complete": False,
                "missing_observed_fields": [
                    "gas_cost_usd",
                    "quote_delay_ms",
                ],
                "simulation_drift": {
                    "liquidity": {
                        "paper_usd": None,
                        "observed_usd": 50000.0,
                        "delta_usd": None,
                    },
                    "sellability": {
                        "paper": None,
                        "observed": "SELLABILITY_OK",
                        "changed": None,
                    },
                    "drift": {},
                },
            },
        },
    )

    drift = result["simulation_drift"]

    assert drift["state"] == "INSUFFICIENT_EVIDENCE"
    assert drift["comparison_complete"] is False
    assert drift["comparable_evidence_count"] == 2
    assert "gas_cost_usd" in drift["missing_observed_fields"]
    assert drift["sellability"]["changed"] is None

    assert result["decision"]["blockers"] == []
    assert drift["decision_authority"] is False
    assert drift["execution_authority"] is False
    assert drift["hardblock_override_authority"] is False


def test_command_center_drift_absent_is_unknown():
    result = build_command_center_readmodel(
        candidate={"token": "0xnone"},
        pipeline_data={},
    )

    drift = result["simulation_drift"]

    assert drift["state"] == "UNKNOWN"
    assert drift["comparison_complete"] is False
    assert drift["comparable_evidence_count"] == 0
    assert drift["decision_authority"] is False
    assert drift["execution_authority"] is False
