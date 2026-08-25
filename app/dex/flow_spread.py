import math


def _num(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def _unknown():
    return {
        "state": "UNKNOWN",
        "buy_flow": None,
        "sell_flow": None,
        "net_flow": None,
        "spread": None,
        "velocity": None,
        "acceleration": None,
        "buy_probability_mean": None,
        "buy_probability_variance": None,
        "buy_probability_std": None,
        "posterior_alpha": None,
        "posterior_beta": None,
        "probability_model": "BETA_BINOMIAL",
        "decision_authority": False,
        "execution_authority": False,
    }


def _beta_binomial_probability(buy, sell):
    if buy < 0 or sell < 0:
        return None

    alpha = 1.0 + buy
    beta = 1.0 + sell
    total = alpha + beta

    mean = alpha / total
    variance = (
        alpha * beta
        / (
            total
            * total
            * (total + 1.0)
        )
    )

    return {
        "buy_probability_mean": mean,
        "buy_probability_variance": variance,
        "buy_probability_std": math.sqrt(variance),
        "posterior_alpha": alpha,
        "posterior_beta": beta,
        "probability_model": "BETA_BINOMIAL",
    }


def flow_spread(
    buy_flow,
    sell_flow,
    prev_spread=None,
    prev_velocity=None,
    freshness="FRESH",
    coverage=1.0,
):
    coverage_value = _num(coverage)

    if (
        freshness != "FRESH"
        or coverage_value is None
        or coverage_value < 1.0
    ):
        return _unknown()

    buy = _num(buy_flow)
    sell = _num(sell_flow)

    if (
        buy is None
        or sell is None
        or buy < 0
        or sell < 0
    ):
        return _unknown()

    spread = buy - sell

    previous_spread = _num(prev_spread)
    velocity = (
        None
        if previous_spread is None
        else spread - previous_spread
    )

    previous_velocity = _num(prev_velocity)
    acceleration = (
        None
        if velocity is None or previous_velocity is None
        else velocity - previous_velocity
    )

    probability = _beta_binomial_probability(
        buy,
        sell,
    )

    return {
        "state": "READY",
        "buy_flow": buy,
        "sell_flow": sell,
        "net_flow": spread,
        "spread": spread,
        "velocity": velocity,
        "acceleration": acceleration,
        **probability,
        "decision_authority": False,
        "execution_authority": False,
    }
