from app.pipeline.execution_context import (
    build_execution_context,
)


def test_context_uses_real_tax_evidence():
    result = build_execution_context(
        market_context={
            "trade_size_usd": 500,
            "slippage_pct": 0.4,
        },
        risk={
            "buy_tax": 2,
            "sell_tax": 4,
        },
    )

    assert (
        result["trade_size_usd"]
        == 500
    )

    assert result[
        "buy_tax_pct"
    ] == 2

    assert result[
        "sell_tax_pct"
    ] == 4

    assert result[
        "slippage_pct"
    ] == 0.4


def test_missing_values_are_not_defaulted():
    result = build_execution_context(
        market_context={},
        risk={},
    )

    assert all(
        value is None
        for value
        in result.values()
    )


def test_gas_units_are_not_misread_as_usd():
    result = build_execution_context(
        market_context={},
        risk={
            "buy_gas": "150000",
            "sell_gas": "175000",
        },
    )

    assert (
        result["gas_cost_usd"]
        is None
    )
