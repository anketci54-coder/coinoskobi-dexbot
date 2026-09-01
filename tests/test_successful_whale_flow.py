from app.dex.successful_whale_flow import analyze_successful_whale_flow


def successful_performance():
    return {
        "state": "SUCCESSFUL",
        "realized_sample_size": 20,
        "realized_win_rate": 0.65,
        "realized_average_return_pct": 4.0,
    }


def test_reputation_alone_never_creates_whale_evidence():
    result = analyze_successful_whale_flow(
        [{
            "wallet_id": "bsc:0xaaa",
            "performance": successful_performance(),
            "value_usd": 80000,
            "inflow_usd": 10000,
            "outflow_usd": 0,
        }],
        total_market_value=100000,
    )
    assert result["state"] == "NO_SUCCESSFUL_WHALE_EVIDENCE"
    assert result["successful_whale_count"] == 0
    assert result["trade_signal"] is False
    assert result["execution_authority"] is False


def test_successful_wallet_with_explicit_whale_evidence_is_composed():
    result = analyze_successful_whale_flow(
        [{
            "wallet_id": "bsc:0xaaa",
            "performance": successful_performance(),
            "is_whale_evidence": True,
            "value_usd": 80000,
            "inflow_usd": 10000,
            "outflow_usd": 1000,
        }],
        total_market_value=100000,
    )
    assert result["state"] == "CONCENTRATED"
    assert "SINGLE_WHALE_DOMINANCE" in result["tags"]
    assert "WHALE_NET_INFLOW" in result["tags"]
    assert result["successful_whale_count"] == 1
    assert result["successful_whale_wallets"] == ["bsc:0xaaa"]
    assert result["decision_authority"] is False
    assert result["wallet_authority"] is False


def test_unproven_or_unsuccessful_wallets_are_excluded():
    result = analyze_successful_whale_flow(
        [
            {
                "wallet_id": "bsc:0xaaa",
                "performance": {"state": "OBSERVED"},
                "is_whale_evidence": True,
                "value_usd": 90000,
            },
            {
                "wallet_id": "bsc:0xbbb",
                "performance": successful_performance(),
                "is_whale_evidence": False,
                "value_usd": 90000,
            },
        ],
        total_market_value=100000,
    )
    assert result["state"] == "NO_SUCCESSFUL_WHALE_EVIDENCE"
    assert result["successful_whale_count"] == 0


def test_stale_source_is_unknown():
    result = analyze_successful_whale_flow([], total_market_value=100000, freshness="STALE")
    assert result["state"] == "UNKNOWN"
    assert result["trade_signal"] is False
