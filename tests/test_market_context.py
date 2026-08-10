from app.pipeline.market_context import (
    build_market_context,
)


def test_candidate_liquidity_maps_to_context():
    result = build_market_context({
        "liquidity": 25_000,
    })

    assert (
        result["liquidity_usd"]
        == 25_000
    )

    assert (
        result["trade_size_usd"]
        is None
    )

    assert (
        result["price_impact_pct"]
        is None
    )

    assert (
        result["slippage_pct"]
        is None
    )


def test_real_execution_fields_are_preserved():
    result = build_market_context({
        "liquidity": 100_000,
        "trade_size_usd": 500,
        "price_impact_pct": 0.4,
        "slippage_pct": 0.6,
    })

    assert result == {
        "liquidity_usd": 100_000.0,
        "trade_size_usd": 500.0,
        "price_impact_pct": 0.4,
        "slippage_pct": 0.6,
    }


def test_missing_values_are_not_fabricated():
    result = build_market_context({})

    assert result == {
        "liquidity_usd": None,
        "trade_size_usd": None,
        "price_impact_pct": None,
        "slippage_pct": None,
    }


def test_invalid_negative_values_become_unknown():
    result = build_market_context({
        "liquidity": -1,
        "trade_size_usd": -1,
        "price_impact_pct": -1,
        "slippage_pct": -1,
    })

    assert all(
        value is None
        for value in result.values()
    )
