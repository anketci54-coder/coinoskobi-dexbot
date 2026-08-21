import json
import math
from statistics import fmean


def _number(value):
    try:
        if value is None:
            return None

        value = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    return (
        value
        if math.isfinite(value)
        else None
    )


def _positive_series(
    values,
):
    result = []

    for value in (
        values
        or ()
    ):
        number = _number(
            value
        )

        if (
            number is not None
            and number > 0
        ):
            result.append(
                number
            )

    return result


def _retention(
    *fractions,
):
    value = 1.0

    for fraction in fractions:
        number = _number(
            fraction
        )

        if number is None:
            continue

        number = min(
            1.0,
            max(
                0.0,
                number,
            ),
        )

        value *= (
            1.0 - number
        )

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def market_statistics(
    prices,
):
    prices = _positive_series(
        prices
    )

    if len(prices) < 2:
        return {
            "ready": False,

            "reason": (
                "PRICE_SERIES_INSUFFICIENT"
            ),

            "prices": prices,

            "log_returns": [],
        }

    returns = [
        math.log(
            right / left
        )
        for left, right
        in zip(
            prices,
            prices[1:],
        )
        if (
            left > 0
            and right > 0
        )
    ]

    if not returns:
        return {
            "ready": False,

            "reason": (
                "RETURN_SERIES_EMPTY"
            ),

            "prices": prices,

            "log_returns": [],
        }

    mean_return = fmean(
        returns
    )

    second_moment = fmean(
        value * value
        for value in returns
    )

    variance = fmean(
        (
            value
            - mean_return
        ) ** 2
        for value in returns
    )

    rms_move = math.sqrt(
        second_moment
    )

    running_peak = prices[0]

    drawdowns = []

    for price in prices:
        running_peak = max(
            running_peak,
            price,
        )

        drawdowns.append(
            math.log(
                running_peak
                / price
            )
        )

    max_drawdown = (
        max(drawdowns)
        if drawdowns
        else 0.0
    )

    risk_log_distance = max(
        rms_move,
        max_drawdown,
    )

    horizon_log_move = sum(
        returns
    )

    return {
        "ready": (
            risk_log_distance > 0
        ),

        "reason": (
            "READY"
            if risk_log_distance > 0
            else (
                "RISK_DISTANCE_UNOBSERVABLE"
            )
        ),

        "prices": prices,

        "log_returns": (
            returns
        ),

        "mean_log_return": (
            mean_return
        ),

        "variance": variance,

        "second_moment": (
            second_moment
        ),

        "rms_log_move": (
            rms_move
        ),

        "max_drawdown_log": (
            max_drawdown
        ),

        "risk_log_distance": (
            risk_log_distance
        ),

        "horizon_log_move": (
            horizon_log_move
        ),
    }


def build_cost_model(
    sellability_data=None,
    exit_evidence=None,
):
    sellability = dict(
        sellability_data
        or {}
    )

    exit_data = dict(
        exit_evidence
        or {}
    )

    route_friction = _number(
        exit_data.get(
            "route_friction_fraction"
        )
    )

    buy_tax_pct = _number(
        sellability.get(
            "buy_tax"
        )
    )

    sell_tax_pct = _number(
        sellability.get(
            "sell_tax"
        )
    )

    buy_gas_units = _number(
        sellability.get(
            "buy_gas"
        )
    )

    sell_gas_units = _number(
        sellability.get(
            "sell_gas"
        )
    )

    gas_price_wei = _number(
        exit_data.get(
            "gas_price_wei"
        )
    )

    wbnb_usd = _number(
        exit_data.get(
            "wbnb_usd_estimate"
        )
    )

    buy_tax = (
        max(
            0.0,
            buy_tax_pct,
        )
        / 100.0
        if buy_tax_pct
        is not None
        else None
    )

    sell_tax = (
        max(
            0.0,
            sell_tax_pct,
        )
        / 100.0
        if sell_tax_pct
        is not None
        else None
    )

    def gas_usd(
        units,
    ):
        if (
            units is None
            or gas_price_wei
            is None
            or wbnb_usd
            is None
        ):
            return None

        return (
            units
            * gas_price_wei
            / 1e18
            * wbnb_usd
        )

    buy_gas_usd = gas_usd(
        buy_gas_units
    )

    sell_gas_usd = gas_usd(
        sell_gas_units
    )

    unknown = []

    if route_friction is None:
        unknown.append(
            "ROUTE_FRICTION"
        )

    if buy_tax is None:
        unknown.append(
            "BUY_TAX"
        )

    if sell_tax is None:
        unknown.append(
            "SELL_TAX"
        )

    if buy_gas_usd is None:
        unknown.append(
            "BUY_GAS_USD"
        )

    if sell_gas_usd is None:
        unknown.append(
            "SELL_GAS_USD"
        )

    # No arbitrary monetary MEV estimate
    # is invented.
    unknown.append(
        "MEV_MONETARY_COST"
    )

    route = max(
        0.0,
        route_friction
        or 0.0,
    )

    buy_retention = _retention(
        route,
        buy_tax,
    )

    sell_retention = _retention(
        route,
        sell_tax,
    )

    return {
        "route_friction_fraction": (
            route_friction
        ),

        "buy_tax_fraction": (
            buy_tax
        ),

        "sell_tax_fraction": (
            sell_tax
        ),

        "buy_gas_usd": (
            buy_gas_usd
        ),

        "sell_gas_usd": (
            sell_gas_usd
        ),

        "buy_retention_known": (
            buy_retention
        ),

        "sell_retention_known": (
            sell_retention
        ),

        "unknown_components": (
            unknown
        ),

        "cost_complete": (
            not unknown
        ),

        "net_semantics": (
            "FULL_NET"
            if not unknown
            else (
                "KNOWN_COMPONENT_NET_ONLY"
            )
        ),
    }


def buy_token_amount(
    entry_amount_usdt,
    entry_price,
    cost_model,
):
    amount = max(
        0.0,
        _number(
            entry_amount_usdt
        )
        or 0.0,
    )

    price = _number(
        entry_price
    )

    if (
        price is None
        or price <= 0
    ):
        return 0.0

    gas = (
        _number(
            (
                cost_model
                or {}
            ).get(
                "buy_gas_usd"
            )
        )
        or 0.0
    )

    retention = _number(
        (
            cost_model
            or {}
        ).get(
            "buy_retention_known"
        )
    )

    if retention is None:
        retention = 1.0

    spend_after_gas = max(
        0.0,
        amount - gas,
    )

    return (
        spend_after_gas
        * retention
        / price
    )


def exit_net_proceeds(
    token_amount,
    price,
    cost_model,
    *,
    charge_gas=True,
):
    tokens = max(
        0.0,
        _number(
            token_amount
        )
        or 0.0,
    )

    price = max(
        0.0,
        _number(price)
        or 0.0,
    )

    retention = _number(
        (
            cost_model
            or {}
        ).get(
            "sell_retention_known"
        )
    )

    if retention is None:
        retention = 1.0

    gas = 0.0

    if (
        charge_gas
        and tokens > 0
    ):
        gas = (
            _number(
                (
                    cost_model
                    or {}
                ).get(
                    "sell_gas_usd"
                )
            )
            or 0.0
        )

    return max(
        0.0,
        (
            tokens
            * price
            * retention
            - gas
        ),
    )


def _score_from_edge_and_risk(
    edge_fraction,
    risk_fraction,
):
    edge = max(
        0.0,
        _number(
            edge_fraction
        )
        or 0.0,
    )

    risk = max(
        0.0,
        _number(
            risk_fraction
        )
        or 0.0,
    )

    total = (
        edge + risk
    )

    if total <= 0:
        return None

    return (
        100.0
        * edge
        / total
    )


def build_trade_plan(
    *,
    entry_price,
    available_capital_usdt,
    price_series,
    quote_reserve_usd,
    lp_protected_fraction,
    sellability_status,
    hard_block=False,
    sellability_data=None,
    exit_evidence=None,
    market_context=None,
):
    entry = _number(
        entry_price
    )

    capital = max(
        0.0,
        _number(
            available_capital_usdt
        )
        or 0.0,
    )

    quote_reserve = max(
        0.0,
        _number(
            quote_reserve_usd
        )
        or 0.0,
    )

    protected = _number(
        lp_protected_fraction
    )

    if protected is not None:
        protected = min(
            1.0,
            max(
                0.0,
                protected,
            ),
        )

    stats = market_statistics(
        price_series
    )

    costs = build_cost_model(
        sellability_data,
        exit_evidence,
    )

    blockers = []

    unknowns = list(
        costs[
            "unknown_components"
        ]
    )

    if hard_block:
        blockers.append(
            "HARD_BLOCK"
        )

    if (
        entry is None
        or entry <= 0
    ):
        blockers.append(
            "ENTRY_PRICE_UNAVAILABLE"
        )

    if capital <= 0:
        blockers.append(
            "CAPITAL_UNAVAILABLE"
        )

    if not stats.get(
        "ready"
    ):
        blockers.append(
            stats.get(
                "reason"
            )
            or (
                "MARKET_STATISTICS_UNAVAILABLE"
            )
        )

    if quote_reserve <= 0:
        blockers.append(
            "QUOTE_RESERVE_UNAVAILABLE"
        )

    if protected is None:
        unknowns.append(
            "LP_PROTECTION_FRACTION"
        )

        blockers.append(
            "LP_PROTECTION_UNKNOWN"
        )

    elif protected <= 0:
        blockers.append(
            "NO_VERIFIED_PERSISTENT_LIQUIDITY"
        )

    gross_log_edge = (
        _number(
            stats.get(
                "horizon_log_move"
            )
        )
        or 0.0
    )

    buy_retention = (
        costs[
            "buy_retention_known"
        ]
    )

    sell_retention = (
        costs[
            "sell_retention_known"
        ]
    )

    retention = (
        buy_retention
        * sell_retention
    )

    friction_log = (
        -math.log(retention)
        if (
            retention > 0
            and retention <= 1
        )
        else math.inf
    )

    known_net_log_edge = (
        gross_log_edge
        - friction_log
    )

    edge_fraction = (
        math.expm1(
            known_net_log_edge
        )
        if math.isfinite(
            known_net_log_edge
        )
        else -1.0
    )

    if known_net_log_edge <= 0:
        blockers.append(
            "KNOWN_COMPONENT_EDGE_NOT_POSITIVE"
        )

    second_moment = (
        _number(
            stats.get(
                "second_moment"
            )
        )
        or 0.0
    )

    if second_moment <= 0:
        blockers.append(
            "RETURN_RISK_UNOBSERVABLE"
        )

        kelly_fraction = 0.0

    else:
        # Full Kelly, bounded only by
        # the physical no-leverage wallet limit.
        kelly_fraction = min(
            1.0,
            max(
                0.0,
                (
                    known_net_log_edge
                    / second_moment
                ),
            ),
        )

    safe_quote_reserve = (
        quote_reserve
        * protected
        if protected
        is not None
        else 0.0
    )

    # Constant-product liquidity cap:
    # position notional is bounded by
    # verified persistent quote liquidity
    # multiplied by the observed positive edge.
    liquidity_edge_cap = (
        safe_quote_reserve
        * max(
            0.0,
            edge_fraction,
        )
    )

    kelly_cap = (
        capital
        * kelly_fraction
    )

    entry_amount = min(
        capital,
        kelly_cap,
        liquidity_edge_cap,
    )

    if entry_amount <= 0:
        blockers.append(
            "MATHEMATICAL_POSITION_SIZE_ZERO"
        )

    token_amount = (
        buy_token_amount(
            entry_amount,
            entry or 0.0,
            costs,
        )
    )

    risk_log_distance = (
        _number(
            stats.get(
                "risk_log_distance"
            )
        )
        or 0.0
    )

    initial_sl = (
        entry
        * math.exp(
            -risk_log_distance
        )
        if (
            entry
            and risk_log_distance > 0
        )
        else None
    )

    floor_value = (
        exit_net_proceeds(
            token_amount,
            initial_sl,
            costs,
        )
        if initial_sl
        is not None
        else 0.0
    )

    initial_risk = max(
        0.0,
        (
            entry_amount
            - floor_value
        ),
    )

    sell_ret = (
        costs[
            "sell_retention_known"
        ]
    )

    sell_gas = (
        costs.get(
            "sell_gas_usd"
        )
        or 0.0
    )

    tp1_activation_price = None

    if (
        token_amount > 0
        and sell_ret > 0
    ):
        # First price where realizing
        # the measured initial risk
        # becomes mathematically feasible.
        tp1_activation_price = (
            (
                entry_amount
                + initial_risk
                + sell_gas
            )
            / (
                token_amount
                * sell_ret
            )
        )

    risk_fraction = (
        (
            1.0
            - math.exp(
                -risk_log_distance
            )
        )
        if risk_log_distance > 0
        else 0.0
    )

    mathematical_score = (
        _score_from_edge_and_risk(
            max(
                0.0,
                edge_fraction,
            ),
            risk_fraction,
        )
    )

    sellability_status = str(
        sellability_status
        or "UNKNOWN"
    ).upper()

    paper_eligible = (
        not blockers
    )

    return {
        "contract": (
            "mathematical_trade_plan"
        ),

        "paper_eligible": (
            paper_eligible
        ),

        # Paper planning never grants
        # live/wallet authority.
        "live_eligible": False,

        "wallet_authority": False,
        "execution_authority": False,

        "hard_block": bool(
            hard_block
        ),

        "blockers": sorted(
            set(blockers)
        ),

        "unknowns": sorted(
            set(unknowns)
        ),

        "sellability_status": (
            sellability_status
        ),

        "entry": {
            "price": entry,

            "band_low": (
                initial_sl
            ),

            "band_high": entry,

            "rule": (
                "CURRENT_PRICE_WITHIN_"
                "EMPIRICAL_RISK_ENVELOPE"
            ),
        },

        "capital": {
            "available_usdt": (
                capital
            ),

            "kelly_fraction": (
                kelly_fraction
            ),

            "kelly_cap_usdt": (
                kelly_cap
            ),

            "safe_quote_reserve_usd": (
                safe_quote_reserve
            ),

            "liquidity_edge_cap_usdt": (
                liquidity_edge_cap
            ),

            "entry_amount_usdt": (
                entry_amount
            ),

            "position_fraction_of_available": (
                (
                    entry_amount
                    / capital
                )
                if capital > 0
                else 0.0
            ),
        },

        "position": {
            "token_amount": (
                token_amount
            ),

            "initial_risk_usdt": (
                initial_risk
            ),
        },

        "sl": {
            "initial_price": (
                initial_sl
            ),

            "risk_log_distance": (
                risk_log_distance
            ),

            "rule": (
                "MONOTONIC_EMPIRICAL_"
                "TREND_FLOOR"
            ),
        },

        "tp1": {
            "static_fraction": None,

            "activation_price": (
                tp1_activation_price
            ),

            "realization_rule": (
                "REALIZE_MINIMUM_PROFIT_NEEDED_"
                "TO_NEUTRALIZE_INITIAL_RISK_AT_"
                "LOCAL_MINIMUM_REQUIRED_FRACTION"
            ),
        },

        "tp2": {
            "static_fraction": None,

            "activation_price": None,

            "realization_rule": (
                "RECOVER_REMAINING_PRINCIPAL_"
                "AT_LOCAL_MINIMUM_REQUIRED_FRACTION"
            ),
        },

        "runner": {
            "static_tp_price": None,

            "rule": (
                "FOLLOW_MONOTONIC_EMPIRICAL_"
                "TREND_FLOOR_UNTIL_BREAK"
            ),
        },

        "statistics": stats,

        "cost_model": costs,

        "expected": {
            "gross_horizon_log_edge": (
                gross_log_edge
            ),

            "known_net_horizon_log_edge": (
                known_net_log_edge
            ),

            "known_net_edge_fraction": (
                edge_fraction
            ),

            "full_net_edge_fraction": (
                edge_fraction
                if costs[
                    "cost_complete"
                ]
                else None
            ),
        },

        "score": {
            "value": (
                mathematical_score
            ),

            "meaning": (
                "EDGE_TO_EMPIRICAL_RISK_"
                "RATIO_NORMALIZED_0_100"
            ),

            "decision_threshold": None,

            "formula": (
                "100*positive_edge/"
                "(positive_edge+empirical_risk)"
            ),

            "authority": False,
        },

        "market_context": dict(
            market_context
            or {}
        ),

        "formulas": {
            "kelly": (
                "known_net_log_edge/"
                "mean_squared_log_return;"
                "capped only by no-leverage wallet boundary"
            ),

            "liquidity_cap": (
                "verified_persistent_quote_reserve"
                "*positive_known_edge_fraction"
            ),

            "initial_sl": (
                "entry*exp(-empirical_risk_log_distance)"
            ),

            "tp1_amount": (
                "minimum realized profit required "
                "to neutralize initial measured risk"
            ),

            "tp2_amount": (
                "minimum net proceeds required "
                "to recover remaining original principal"
            ),

            "runner_exit": (
                "highest_price*"
                "exp(-updated_empirical_risk_log_distance);"
                "monotonic"
            ),
        },
    }


def dynamic_stop_price(
    *,
    prices,
    highest_price,
    previous_stop,
    fallback_distance=None,
):
    stats = market_statistics(
        prices
    )

    distance = _number(
        stats.get(
            "risk_log_distance"
        )
    )

    if (
        distance is None
        or distance <= 0
    ):
        distance = _number(
            fallback_distance
        )

    highest = _number(
        highest_price
    )

    previous = max(
        0.0,
        _number(
            previous_stop
        )
        or 0.0,
    )

    if (
        highest is None
        or highest <= 0
        or distance is None
        or distance <= 0
    ):
        return (
            previous
            or None
        )

    candidate = (
        highest
        * math.exp(
            -distance
        )
    )

    # Long protection can never loosen.
    return max(
        previous,
        candidate,
    )


def initial_net_risk_usdt(
    token_amount,
    entry_amount_usdt,
    stop_price,
    cost_model,
):
    import math

    try:
        tokens = float(token_amount)
        entry_amount = float(
            entry_amount_usdt
        )
        stop = float(stop_price)
    except (TypeError, ValueError):
        return None

    if not all(
        math.isfinite(value)
        for value in (
            tokens,
            entry_amount,
            stop,
        )
    ):
        return None

    if (
        tokens <= 0
        or entry_amount <= 0
        or stop <= 0
    ):
        return None

    stop_proceeds = (
        exit_net_proceeds(
            tokens,
            stop,
            cost_model or {},
        )
    )

    try:
        stop_proceeds = float(
            stop_proceeds
        )
    except (TypeError, ValueError):
        return None

    if not math.isfinite(
        stop_proceeds
    ):
        return None

    return max(
        0.0,
        entry_amount
        - stop_proceeds,
    )

def tp1_required_fraction(
    token_amount,
    remaining_cost_basis_usdt,
    current_price,
    initial_risk_usdt,
    realized_pnl_usdt,
    cost_model,
):
    import math

    try:
        tokens = float(token_amount)
        basis = float(
            remaining_cost_basis_usdt
        )
        price = float(current_price)
        initial_risk = float(
            initial_risk_usdt
        )
        realized_pnl = float(
            realized_pnl_usdt
            or 0.0
        )
    except (TypeError, ValueError):
        return None

    if not all(
        math.isfinite(value)
        for value in (
            tokens,
            basis,
            price,
            initial_risk,
            realized_pnl,
        )
    ):
        return None

    if (
        tokens <= 0
        or basis < 0
        or price <= 0
        or initial_risk < 0
    ):
        return None

    target = max(
        0.0,
        initial_risk
        - realized_pnl,
    )

    if target <= 0:
        return 0.0

    def pnl_at(close_fraction):
        sold_tokens = (
            tokens
            * close_fraction
        )

        sold_basis = (
            basis
            * close_fraction
        )

        proceeds = exit_net_proceeds(
            sold_tokens,
            price,
            cost_model or {},
        )

        try:
            proceeds = float(
                proceeds
            )
        except (TypeError, ValueError):
            return None

        pnl = (
            proceeds
            - sold_basis
        )

        if not math.isfinite(pnl):
            return None

        return pnl

    maximum = pnl_at(1.0)

    if (
        maximum is None
        or maximum < target
    ):
        return None

    low = 0.0
    high = 1.0

    for _ in range(80):
        middle = (
            low + high
        ) / 2.0

        value = pnl_at(
            middle
        )

        if value is None:
            return None

        if value >= target:
            high = middle
        else:
            low = middle

    if not (
        0.0 < high < 1.0
    ):
        return None

    return high


def tp2_required_fraction(
    token_amount,
    current_price,
    original_entry_usdt,
    realized_proceeds_usdt,
    cost_model,
):
    import math

    try:
        tokens = float(token_amount)
        price = float(current_price)
        original_entry = float(
            original_entry_usdt
        )
        realized_proceeds = float(
            realized_proceeds_usdt
            or 0.0
        )
    except (TypeError, ValueError):
        return None

    if not all(
        math.isfinite(value)
        for value in (
            tokens,
            price,
            original_entry,
            realized_proceeds,
        )
    ):
        return None

    if (
        tokens <= 0
        or price <= 0
        or original_entry < 0
    ):
        return None

    target = max(
        0.0,
        original_entry
        - realized_proceeds,
    )

    if target <= 0:
        return 0.0

    def proceeds_at(close_fraction):
        proceeds = exit_net_proceeds(
            tokens * close_fraction,
            price,
            cost_model or {},
        )

        try:
            proceeds = float(
                proceeds
            )
        except (TypeError, ValueError):
            return None

        if not math.isfinite(
            proceeds
        ):
            return None

        return proceeds

    maximum = proceeds_at(1.0)

    if (
        maximum is None
        or maximum < target
    ):
        return None

    low = 0.0
    high = 1.0

    for _ in range(80):
        middle = (
            low + high
        ) / 2.0

        value = proceeds_at(
            middle
        )

        if value is None:
            return None

        if value >= target:
            high = middle
        else:
            low = middle

    if not (
        0.0 < high < 1.0
    ):
        return None

    return high


def realization_values(
    token_amount,
    fraction,
    current_price,
    remaining_cost_basis_usdt,
    cost_model,
):
    import math

    try:
        tokens = float(token_amount)
        close_fraction = float(fraction)
        price = float(current_price)
        basis = float(
            remaining_cost_basis_usdt
        )
    except (TypeError, ValueError):
        return None

    if not all(
        math.isfinite(value)
        for value in (
            tokens,
            close_fraction,
            price,
            basis,
        )
    ):
        return None

    if (
        tokens <= 0
        or price <= 0
        or basis < 0
        or close_fraction <= 0
        or close_fraction > 1
    ):
        return None

    sold_tokens = (
        tokens
        * close_fraction
    )

    remaining_tokens = (
        tokens
        - sold_tokens
    )

    sold_cost_basis = (
        basis
        * close_fraction
    )

    remaining_cost_basis = (
        basis
        - sold_cost_basis
    )

    if (
        sold_tokens <= 0
        or sold_tokens > tokens
        or remaining_tokens < 0
        or sold_cost_basis < 0
        or remaining_cost_basis < 0
    ):
        return None

    gross_proceeds = (
        sold_tokens
        * price
    )

    net_proceeds = exit_net_proceeds(
        sold_tokens,
        price,
        cost_model or {},
    )

    try:
        net_proceeds = float(
            net_proceeds
        )
    except (TypeError, ValueError):
        return None

    if not math.isfinite(
        net_proceeds
    ):
        return None

    realized_pnl = (
        net_proceeds
        - sold_cost_basis
    )

    if not math.isfinite(
        realized_pnl
    ):
        return None

    return {
        "fraction": close_fraction,
        "sold_tokens": sold_tokens,
        "remaining_tokens": remaining_tokens,
        "gross_proceeds_usdt": gross_proceeds,
        "net_proceeds_usdt": net_proceeds,
        "sold_cost_basis_usdt": sold_cost_basis,
        "remaining_cost_basis_usdt": (
            remaining_cost_basis
        ),
        "realized_pnl_usdt": realized_pnl,
    }


def decode_plan(raw):
    if isinstance(
        raw,
        dict,
    ):
        return dict(raw)

    if not raw:
        return None

    try:
        value = json.loads(
            raw
        )

    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None

    return (
        value
        if isinstance(
            value,
            dict,
        )
        else None
    )
