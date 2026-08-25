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
            "informative_return_count": 0,
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
            "informative_return_count": 0,
        }

    informative_returns = [
        value
        for value in returns
        if value != 0.0
    ]

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
                running_peak / price
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
        "log_returns": returns,
        "informative_return_count": (
            len(informative_returns)
        ),
        "mean_log_return": mean_return,
        "variance": variance,
        "second_moment": second_moment,
        "rms_log_move": rms_move,
        "max_drawdown_log": max_drawdown,
        "risk_log_distance": (
            risk_log_distance
        ),
        "horizon_log_move": (
            horizon_log_move
        ),
    }



def mathematical_vur_kac_state(
    *,
    prices,
    token_amount,
    remaining_cost_basis_usdt,
    current_price,
    cost_model,
    signal_bundle=None,
):
    """
    Mathematical short-horizon realization state.

    No fixed ROI target.
    No fixed close fraction.
    No fixed clock window.

    Uses:
    - post-entry observed log returns
    - measured price acceleration
    - fresh/full native flow momentum
    - fresh/full native flow acceleration
    - measured RMS/drawdown risk distance
    - current net exit value under the canonical cost model
    """

    series = _positive_series(
        prices
    )

    current = _number(
        current_price
    )

    tokens = max(
        0.0,
        _number(
            token_amount
        )
        or 0.0,
    )

    basis = max(
        0.0,
        _number(
            remaining_cost_basis_usdt
        )
        or 0.0,
    )

    signal = (
        dict(signal_bundle)
        if isinstance(
            signal_bundle,
            dict,
        )
        else {}
    )

    def unknown(reason):
        return {
            "ready": False,
            "reason": reason,
            "realize": False,
            "continuation_positive": False,
            "continuation_edge_usdt": None,
            "remaining_net_profit_usdt": None,
            "latest_log_return": None,
            "previous_log_return": None,
            "price_acceleration": None,
            "risk_log_distance": None,
            "flow_momentum": None,
            "flow_acceleration": None,
            "projected_conservative_price": None,
            "current_net_exit_usdt": None,
            "projected_net_exit_usdt": None,
            "decision_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    if (
        current is None
        or current <= 0
        or tokens <= 0
    ):
        return unknown(
            "POSITION_VALUE_UNAVAILABLE"
        )

    # Two consecutive returns are the minimum
    # mathematical requirement for an acceleration.
    if len(series) < 3:
        return unknown(
            "POST_ENTRY_SERIES_INSUFFICIENT"
        )

    returns = [
        math.log(
            right / left
        )
        for left, right
        in zip(
            series,
            series[1:],
        )
        if (
            left > 0
            and right > 0
        )
    ]

    if len(returns) < 2:
        return unknown(
            "POST_ENTRY_RETURNS_INSUFFICIENT"
        )

    latest_return = (
        returns[-1]
    )

    previous_return = (
        returns[-2]
    )

    price_acceleration = (
        latest_return
        - previous_return
    )

    stats = market_statistics(
        series
    )

    risk_log_distance = _number(
        stats.get(
            "risk_log_distance"
        )
    )

    if (
        risk_log_distance is None
        or risk_log_distance < 0
    ):
        return unknown(
            "POST_ENTRY_RISK_UNAVAILABLE"
        )

    freshness = str(
        signal.get(
            "freshness"
        )
        or "UNKNOWN"
    ).upper()

    coverage = _number(
        signal.get(
            "coverage"
        )
    )

    flow_momentum = _number(
        signal.get(
            "flow_momentum"
        )
    )

    flow_acceleration = _number(
        signal.get(
            "flow_acceleration"
        )
    )

    # Missing/partial/stale flow remains UNKNOWN.
    if (
        freshness != "FRESH"
        or coverage is None
        or coverage < 1.0
        or flow_momentum is None
        or flow_acceleration is None
        or not (
            -1.0
            <= flow_momentum
            <= 1.0
        )
        or not (
            -1.0
            <= flow_acceleration
            <= 1.0
        )
    ):
        result = unknown(
            "FLOW_EVIDENCE_NOT_READY"
        )

        result[
            "latest_log_return"
        ] = latest_return

        result[
            "previous_log_return"
        ] = previous_return

        result[
            "price_acceleration"
        ] = price_acceleration

        result[
            "risk_log_distance"
        ] = risk_log_distance

        return result

    # One actual observation-step continuation:
    #
    # log(P_next/P_now)
    #     = latest measured momentum
    #       - measured adverse movement distance
    #
    # No fixed target or time horizon is invented.
    conservative_log_move = (
        latest_return
        - risk_log_distance
    )

    try:
        projected_price = (
            current
            * math.exp(
                conservative_log_move
            )
        )
    except OverflowError:
        return unknown(
            "CONTINUATION_PROJECTION_INVALID"
        )

    if (
        not math.isfinite(
            projected_price
        )
        or projected_price <= 0
    ):
        return unknown(
            "CONTINUATION_PROJECTION_INVALID"
        )

    current_net_exit = (
        exit_net_proceeds(
            tokens,
            current,
            cost_model or {},
        )
    )

    projected_net_exit = (
        exit_net_proceeds(
            tokens,
            projected_price,
            cost_model or {},
        )
    )

    continuation_edge = (
        projected_net_exit
        - current_net_exit
    )

    remaining_net_profit = (
        current_net_exit
        - basis
    )

    price_weakening = (
        latest_return <= 0
        or price_acceleration < 0
    )

    flow_weakening = (
        flow_momentum <= 0
        or flow_acceleration < 0
    )

    continuation_positive = (
        continuation_edge > 0
        and latest_return > 0
        and flow_momentum > 0
        and flow_acceleration >= 0
    )

    realize = (
        remaining_net_profit > 0
        and continuation_edge <= 0
        and price_weakening
        and flow_weakening
    )

    if realize:
        reason = (
            "VUR_KAC_REALIZATION_READY"
        )

    elif remaining_net_profit <= 0:
        reason = (
            "NO_REALIZABLE_NET_PROFIT"
        )

    elif continuation_positive:
        reason = (
            "CONTINUATION_EDGE_POSITIVE"
        )

    elif not price_weakening:
        reason = (
            "PRICE_MOMENTUM_NOT_WEAKENING"
        )

    elif not flow_weakening:
        reason = (
            "FLOW_NOT_WEAKENING"
        )

    else:
        reason = (
            "CONTINUATION_NOT_CONFIRMED"
        )

    return {
        "ready": True,
        "reason": reason,
        "realize": realize,
        "continuation_positive": (
            continuation_positive
        ),
        "continuation_edge_usdt": (
            continuation_edge
        ),
        "remaining_net_profit_usdt": (
            remaining_net_profit
        ),
        "latest_log_return": (
            latest_return
        ),
        "previous_log_return": (
            previous_return
        ),
        "price_acceleration": (
            price_acceleration
        ),
        "risk_log_distance": (
            risk_log_distance
        ),
        "flow_momentum": (
            flow_momentum
        ),
        "flow_acceleration": (
            flow_acceleration
        ),
        "projected_conservative_price": (
            projected_price
        ),
        "current_net_exit_usdt": (
            current_net_exit
        ),
        "projected_net_exit_usdt": (
            projected_net_exit
        ),
        "decision_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
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



def _runtime_admission_evidence_blockers(
    *,
    stats,
    market_context,
):
    context = (
        market_context
        if isinstance(
            market_context,
            dict,
        )
        else {}
    )

    runtime = (
        context.get(
            "runtime_intelligence"
        )
        or {}
    )

    quality = context.get(
        "market_quality"
    )

    if not isinstance(
        quality,
        dict,
    ):
        quality = (
            runtime.get(
                "market_quality"
            )
            if isinstance(
                runtime,
                dict,
            )
            else None
        )

    if not isinstance(
        quality,
        dict,
    ):
        return []

    blockers = []

    informative_count = (
        stats.get(
            "informative_return_count"
        )
    )

    if informative_count is None:
        informative_count = sum(
            1
            for value in (
                stats.get(
                    "log_returns"
                )
                or ()
            )
            if value != 0.0
        )

    if informative_count < 2:
        blockers.append(
            "EMPIRICAL_MOVEMENT_INSUFFICIENT"
        )

    if (
        quality.get(
            "market_evidence_ready"
        )
        is False
    ):
        blockers.append(
            "MARKET_QUALITY_EVIDENCE_NOT_READY"
        )

    if (
        quality.get(
            "suspicious_volume"
        )
        is True
    ):
        blockers.append(
            "SUSPICIOUS_VOLUME"
        )

    participation = str(
        quality.get(
            "participation_state"
        )
        or "UNKNOWN"
    ).upper()

    if participation == "UNKNOWN":
        blockers.append(
            "PARTICIPATION_EVIDENCE_UNKNOWN"
        )

    elif participation == "CONCENTRATED":
        blockers.append(
            "PARTICIPATION_CONCENTRATED"
        )

    liquidity = str(
        quality.get(
            "liquidity_state"
        )
        or "UNKNOWN"
    ).upper()

    if liquidity == "NO_LIQUIDITY":
        blockers.append(
            "MARKET_QUALITY_NO_LIQUIDITY"
        )

    elif (
        liquidity
        == "DETERIORATING_FAST"
    ):
        blockers.append(
            "MARKET_QUALITY_LIQUIDITY_DETERIORATING_FAST"
        )

    return list(
        dict.fromkeys(
            blockers
        )
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

    exit_data = (
        dict(exit_evidence)
        if isinstance(
            exit_evidence,
            dict,
        )
        else {}
    )

    observed_min_quote_reserve = max(
        0.0,
        _number(
            exit_data.get(
                "observed_min_quote_reserve_usd"
            )
        )
        or 0.0,
    )

    reserve_observation_count = max(
        0,
        int(
            _number(
                exit_data.get(
                    "reserve_observation_count"
                )
            )
            or 0
        ),
    )

    # Persistence requires more than one measured reserve observation.
    # This is physical exit-capacity evidence, NOT LP-lock evidence.
    empirical_reserve_ready = (
        observed_min_quote_reserve > 0
        and reserve_observation_count >= 2
    )

    blockers = []

    blockers.extend(
        _runtime_admission_evidence_blockers(
            stats=stats,
            market_context=market_context,
        )
    )

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

        if not empirical_reserve_ready:
            blockers.append(
                "LP_PROTECTION_UNKNOWN"
            )

    elif protected <= 0:
        if not empirical_reserve_ready:
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

    if (
        protected is not None
        and protected > 0
    ):
        safe_quote_reserve = (
            quote_reserve
            * protected
        )

        liquidity_capacity_source = (
            "VERIFIED_LP_PROTECTION"
        )

    elif empirical_reserve_ready:
        safe_quote_reserve = min(
            quote_reserve,
            observed_min_quote_reserve,
        )

        liquidity_capacity_source = (
            "EMPIRICAL_RESERVE_FLOOR"
        )

    else:
        safe_quote_reserve = 0.0

        liquidity_capacity_source = (
            "UNAVAILABLE"
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

            "liquidity_capacity_source": (
                liquidity_capacity_source
            ),

            "observed_min_quote_reserve_usd": (
                observed_min_quote_reserve
                if empirical_reserve_ready
                else None
            ),

            "reserve_observation_count": (
                reserve_observation_count
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
