from app.dex.price_impact import (
    analyze_price_impact,
    constant_product_quote,
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

    assert result["exact_amm_ready"] is False


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


def test_constant_product_quote_requires_real_fee_evidence():
    result = constant_product_quote(
        reserve_in=1000,
        reserve_out=2000,
        amount_in=10,
        fee_fraction=None,
    )

    assert result["state"] == "UNKNOWN"
    assert result["amount_out"] is None


def test_constant_product_quote_matches_fee_aware_formula():
    result = constant_product_quote(
        reserve_in=1000,
        reserve_out=2000,
        amount_in=10,
        fee_fraction=0.0025,
    )

    expected_effective = 10 * (1 - 0.0025)
    expected_out = (
        2000 * expected_effective
        / (1000 + expected_effective)
    )

    assert result["state"] == "READY"
    assert abs(
        result["amount_out"] - expected_out
    ) < 1e-12

    assert result["price_impact_fraction"] > 0
    assert (
        result["total_execution_shortfall_fraction"]
        >= result["price_impact_fraction"]
    )

    assert result["decision_authority"] is False
    assert result["execution_authority"] is False


def test_analyzer_exposes_exact_amm_without_replacing_legacy_context():
    result = analyze_price_impact(
        trade_size_usd=100,
        liquidity_usd=100_000,
        reserve_in=1000,
        reserve_out=2000,
        amount_in=10,
        fee_fraction=0.0025,
    )

    assert result["estimated_impact_context"] == "HEALTHY"
    assert result["exact_amm_ready"] is True
    assert result["exact_amm"]["state"] == "READY"
