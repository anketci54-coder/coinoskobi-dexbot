from app.dex.market_quality import (
    analyze_market_quality,
)


def test_healthy_participation():
    result = analyze_market_quality(
        volume_usd=10_000,
        buy_volume_usd=6_000,
        sell_volume_usd=4_000,
        buyers=30,
        sellers=20,
        buys=40,
        sells=30,
        liquidity_usd=50_000,
        previous_liquidity_usd=45_000,
    )

    assert result["unique_participants"] == 50
    assert result["transaction_count"] == 70
    assert result["participation_state"] == "DIVERSE"
    assert result["liquidity_state"] == "IMPROVING"
    assert result["suspicious_volume"] is False
    assert result["volume_turnover"] == 0.2


def test_concentrated_volume_is_flagged():
    result = analyze_market_quality(
        volume_usd=50_000,
        buyers=1,
        sellers=0,
        buys=50,
        sells=0,
        liquidity_usd=25_000,
    )

    assert result["participation_state"] == "CONCENTRATED"
    assert result["suspicious_volume"] is True


def test_fast_liquidity_deterioration():
    result = analyze_market_quality(
        liquidity_usd=60_000,
        previous_liquidity_usd=100_000,
    )

    assert result["liquidity_change_pct"] == -0.4
    assert (
        result["liquidity_state"]
        == "DETERIORATING_FAST"
    )


def test_missing_previous_liquidity_is_unknown():
    result = analyze_market_quality(
        liquidity_usd=10_000,
    )

    assert result["liquidity_change_pct"] is None
    assert (
        result["liquidity_state"]
        == "STABLE_OR_UNKNOWN"
    )


def test_no_flow():
    result = analyze_market_quality()

    assert result["participation_state"] == "NO_FLOW"
    assert result["transaction_count"] == 0


def test_authority_is_zero():
    result = analyze_market_quality(
        volume_usd=1_000_000,
        buyers=100,
        sellers=100,
        buys=200,
        sells=200,
        liquidity_usd=500_000,
    )

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
