from app.dex.price_impact import (
    analyze_price_impact,
)


def test_small_trade_is_healthy():
    result = analyze_price_impact(
        trade_size_usd=100,
        liquidity_usd=100_000,
    )

    assert (
        result["estimated_impact_context"]
        == "HEALTHY"
    )


def test_large_trade_is_critical():
    result = analyze_price_impact(
        trade_size_usd=20_000,
        liquidity_usd=100_000,
    )

    assert (
        result["estimated_impact_context"]
        == "CRITICAL"
    )


def test_zero_liquidity_unknown():
    result = analyze_price_impact(
        trade_size_usd=100,
        liquidity_usd=0,
    )

    assert (
        result["estimated_impact_context"]
        == "UNKNOWN"
    )
