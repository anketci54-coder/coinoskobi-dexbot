def _number(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if value < 0:
        return None

    return value


def build_execution_context(
    *,
    market_context=None,
    risk=None,
):
    """
    Build execution-cost evidence only from known data.

    No defaults.
    No RPC.
    No HTTP.

    Important:
    sellability simulation may provide taxes,
    but gas units are NOT gas cost in USD.
    They are therefore not monetized here.
    """

    market_context = (
        market_context or {}
    )

    risk = risk or {}

    return {
        "trade_size_usd": _number(
            market_context.get(
                "trade_size_usd"
            )
        ),

        "buy_tax_pct": _number(
            risk.get("buy_tax")
        ),

        "sell_tax_pct": _number(
            risk.get("sell_tax")
        ),

        # These fields must come from real
        # execution/quote evidence later.
        "swap_fee_pct": _number(
            market_context.get(
                "swap_fee_pct"
            )
        ),

        "slippage_pct": _number(
            market_context.get(
                "slippage_pct"
            )
        ),

        "mev_cost_pct": _number(
            market_context.get(
                "mev_cost_pct"
            )
        ),

        "gas_cost_usd": _number(
            market_context.get(
                "gas_cost_usd"
            )
        ),

        # 3K will eventually provide this from
        # Entry / SL / TP economics.
        "expected_gross_edge_pct": (
            _number(
                market_context.get(
                    "expected_gross_edge_pct"
                )
            )
        ),
    }
