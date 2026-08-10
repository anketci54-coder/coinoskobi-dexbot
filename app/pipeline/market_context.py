def _positive_number(value):
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


def build_market_context(row):
    """
    Candidate / execution evidence -> risk context.

    Pure local.
    No RPC.
    No HTTP.
    No DB.

    Important:
    Missing execution evidence stays None.
    No fake/default price-impact or slippage.
    """

    row = row or {}

    return {
        "liquidity_usd": _positive_number(
            row.get("liquidity")
        ),
        "trade_size_usd": _positive_number(
            row.get("trade_size_usd")
        ),
        "price_impact_pct": _positive_number(
            row.get("price_impact_pct")
        ),
        "slippage_pct": _positive_number(
            row.get("slippage_pct")
        ),
    }
