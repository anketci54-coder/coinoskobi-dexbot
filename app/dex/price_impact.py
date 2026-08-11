def _positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(value, 0.0)


def analyze_price_impact(
    *,
    trade_size_usd,
    liquidity_usd,
):
    trade_size = _positive(
        trade_size_usd
    )

    liquidity = _positive(
        liquidity_usd
    )

    ratio = (
        trade_size / liquidity
        if liquidity > 0
        else None
    )

    if ratio is None:
        state = "UNKNOWN"

    elif ratio >= 0.10:
        state = "CRITICAL"

    elif ratio >= 0.03:
        state = "HIGH"

    elif ratio >= 0.01:
        state = "ELEVATED"

    else:
        state = "HEALTHY"

    return {
        "trade_size_usd": trade_size,
        "liquidity_usd": liquidity,
        "trade_liquidity_ratio": ratio,
        "estimated_impact_context": state,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
