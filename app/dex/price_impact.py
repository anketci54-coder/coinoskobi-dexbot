def _positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(value, 0.0)


def _finite_positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if value <= 0:
        return None

    return value


def _fee_fraction(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not 0.0 <= value < 1.0:
        return None

    return value


def max_input_for_price_impact(
    *,
    reserve_in,
    fee_fraction,
    max_price_impact_fraction,
):
    """Invert V2 x*y=k impact to obtain a gross-input capacity.

    The impact bound is an input, not a hidden policy constant. This
    function only converts a caller-provided risk bound into an exact
    reserve-aware capacity.
    """
    x = _finite_positive(reserve_in)
    fee = _fee_fraction(fee_fraction)

    try:
        impact = float(max_price_impact_fraction)
    except (TypeError, ValueError):
        impact = None

    if (
        x is None
        or fee is None
        or impact is None
        or not 0.0 < impact < 1.0
    ):
        return {
            "state": "UNKNOWN",
            "max_amount_in": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    effective_capacity = (
        x * impact
        / (1.0 - impact)
    )

    gross_capacity = (
        effective_capacity
        / (1.0 - fee)
    )

    return {
        "state": "READY",
        "model": "CONSTANT_PRODUCT_V2_INVERSE_IMPACT",
        "reserve_in": x,
        "fee_fraction": fee,
        "max_price_impact_fraction": impact,
        "max_effective_amount_in": effective_capacity,
        "max_amount_in": gross_capacity,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def constant_product_quote(
    *,
    reserve_in,
    reserve_out,
    amount_in,
    fee_fraction,
):
    """Exact fee-aware x*y=k swap math for V2-style pools.

    No fee is assumed. The caller must provide the verified pool fee as
    a fraction (for example 0.0025 for 0.25%). Missing/invalid evidence
    stays UNKNOWN rather than silently using a default.
    """
    x = _finite_positive(reserve_in)
    y = _finite_positive(reserve_out)
    dx = _finite_positive(amount_in)
    fee = _fee_fraction(fee_fraction)

    if (
        x is None
        or y is None
        or dx is None
        or fee is None
    ):
        return {
            "state": "UNKNOWN",
            "amount_out": None,
            "price_impact_fraction": None,
            "total_execution_shortfall_fraction": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    effective_in = dx * (1.0 - fee)

    if effective_in <= 0:
        return {
            "state": "UNKNOWN",
            "amount_out": None,
            "price_impact_fraction": None,
            "total_execution_shortfall_fraction": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    amount_out = (
        y * effective_in
        / (x + effective_in)
    )

    mid_out_per_in = y / x
    execution_out_per_gross_in = amount_out / dx
    execution_out_per_effective_in = amount_out / effective_in

    price_impact_fraction = max(
        0.0,
        1.0
        - (
            execution_out_per_effective_in
            / mid_out_per_in
        ),
    )

    total_execution_shortfall_fraction = max(
        0.0,
        1.0
        - (
            execution_out_per_gross_in
            / mid_out_per_in
        ),
    )

    reserve_in_after = x + dx
    reserve_out_after = y - amount_out

    spot_out_per_in_after = (
        reserve_out_after
        / reserve_in_after
    )

    invariant_before = x * y
    invariant_after = (
        reserve_in_after
        * reserve_out_after
    )

    return {
        "state": "READY",
        "model": "CONSTANT_PRODUCT_V2",
        "reserve_in": x,
        "reserve_out": y,
        "amount_in": dx,
        "fee_fraction": fee,
        "fee_amount_in": dx * fee,
        "effective_amount_in": effective_in,
        "amount_out": amount_out,
        "mid_out_per_in": mid_out_per_in,
        "execution_out_per_gross_in": execution_out_per_gross_in,
        "execution_out_per_effective_in": execution_out_per_effective_in,
        "price_impact_fraction": price_impact_fraction,
        "total_execution_shortfall_fraction": (
            total_execution_shortfall_fraction
        ),
        "reserve_in_after": reserve_in_after,
        "reserve_out_after": reserve_out_after,
        "spot_out_per_in_after": spot_out_per_in_after,
        "invariant_before": invariant_before,
        "invariant_after": invariant_after,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def analyze_price_impact(
    *,
    trade_size_usd,
    liquidity_usd,
    reserve_in=None,
    reserve_out=None,
    amount_in=None,
    fee_fraction=None,
    max_price_impact_fraction=None,
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

    exact = constant_product_quote(
        reserve_in=reserve_in,
        reserve_out=reserve_out,
        amount_in=amount_in,
        fee_fraction=fee_fraction,
    )

    capacity = max_input_for_price_impact(
        reserve_in=reserve_in,
        fee_fraction=fee_fraction,
        max_price_impact_fraction=(
            max_price_impact_fraction
        ),
    )

    return {
        "trade_size_usd": trade_size,
        "liquidity_usd": liquidity,
        "trade_liquidity_ratio": ratio,
        "estimated_impact_context": state,
        "exact_amm": exact,
        "exact_amm_ready": (
            exact.get("state") == "READY"
        ),
        "impact_capacity": capacity,
        "impact_capacity_ready": (
            capacity.get("state") == "READY"
        ),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
