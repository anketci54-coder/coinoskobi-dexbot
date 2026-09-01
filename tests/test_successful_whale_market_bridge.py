from app.dex.successful_whale_flow import analyze_successful_whale_flow
from app.dex.wallet_market_bridge import bind_wallet_market_context


def _successful():
    return {
        "state": "SUCCESSFUL",
        "realized_sample_size": 20,
        "realized_win_rate": 0.65,
        "realized_average_return_pct": 8.0,
    }


def test_successful_whale_flow_is_canonical_bridge_compatible():
    whale = analyze_successful_whale_flow(
        [
            {
                "wallet_id": "bsc:0xaaa",
                "performance": _successful(),
                "is_whale_evidence": True,
                "value_usd": 800.0,
                "inflow_usd": 300.0,
                "outflow_usd": 50.0,
            }
        ],
        total_market_value=1000.0,
    )

    result = bind_wallet_market_context(
        {"state": "READY", "wallet_id": "bsc:0xaaa"},
        {"state": "OBSERVED", "behavior_tags": []},
        {"state": "SELF_ONLY"},
        whale,
        {"state": "NEUTRAL"},
    )

    assert result["wallet_context_ready"] is True
    assert result["whale_state"] == "CONCENTRATED"
    assert "WHALE_NET_INFLOW" in result["whale_tags"]
    assert result["trade_permission"] is False
    assert result["decision_authority"] is False
    assert result["execution_authority"] is False


def test_successful_reputation_without_whale_evidence_stays_unready():
    whale = analyze_successful_whale_flow(
        [
            {
                "wallet_id": "bsc:0xaaa",
                "performance": _successful(),
                "is_whale_evidence": False,
                "value_usd": 800.0,
            }
        ],
        total_market_value=1000.0,
    )

    result = bind_wallet_market_context(
        {"state": "READY", "wallet_id": "bsc:0xaaa"},
        {"state": "OBSERVED", "behavior_tags": []},
        {"state": "SELF_ONLY"},
        whale,
        {"state": "NEUTRAL"},
    )

    assert whale["state"] == "NO_SUCCESSFUL_WHALE_EVIDENCE"
    assert result["trade_permission"] is False
    assert result["decision_authority"] is False
    assert result["execution_authority"] is False
