import math


def _finite(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def _ratio(value):
    value = _finite(value)

    if value is None or not 0.0 <= value <= 1.0:
        return None

    return value


def build_rug_features(
    *,
    mint=None,
    pause=None,
    blacklist=None,
    proxy=None,
    owner_can_change_balance=None,
    owner_can_take_back_ownership=None,
    lp_protected_fraction=None,
    deployer_lp_fraction=None,
    creator_holder_fraction=None,
    holder_hhi=None,
    liquidity_log_change=None,
    liquidity_acceleration=None,
    buy_probability=None,
    wallet_hhi=None,
    wallet_entropy=None,
    pool_age_seconds=None,
):
    """
    Build an evidence-only rug feature vector.

    This function deliberately does NOT emit a rug probability or score.
    A probability requires a fitted and calibrated model with an explicit
    prediction horizon. UNKNOWN evidence remains None rather than becoming
    an automatic negative vote.
    """
    controls = {
        "mint": (
            mint if isinstance(mint, bool) else None
        ),
        "pause": (
            pause if isinstance(pause, bool) else None
        ),
        "blacklist": (
            blacklist if isinstance(blacklist, bool) else None
        ),
        "proxy": (
            proxy if isinstance(proxy, bool) else None
        ),
        "owner_can_change_balance": (
            owner_can_change_balance
            if isinstance(owner_can_change_balance, bool)
            else None
        ),
        "owner_can_take_back_ownership": (
            owner_can_take_back_ownership
            if isinstance(owner_can_take_back_ownership, bool)
            else None
        ),
    }

    features = {
        **controls,
        "lp_protected_fraction": _ratio(
            lp_protected_fraction
        ),
        "deployer_lp_fraction": _ratio(
            deployer_lp_fraction
        ),
        "creator_holder_fraction": _ratio(
            creator_holder_fraction
        ),
        "holder_hhi": _ratio(
            holder_hhi
        ),
        "liquidity_log_change": _finite(
            liquidity_log_change
        ),
        "liquidity_acceleration": _finite(
            liquidity_acceleration
        ),
        "buy_probability": _ratio(
            buy_probability
        ),
        "wallet_hhi": _ratio(
            wallet_hhi
        ),
        "wallet_entropy": _ratio(
            wallet_entropy
        ),
        "pool_age_seconds": _finite(
            pool_age_seconds
        ),
    }

    if (
        features["pool_age_seconds"] is not None
        and features["pool_age_seconds"] < 0
    ):
        features["pool_age_seconds"] = None

    known = sum(
        value is not None
        for value in features.values()
    )

    return {
        "state": (
            "READY" if known else "UNKNOWN"
        ),
        "features": features,
        "known_feature_count": known,
        "total_feature_count": len(features),
        "rug_probability": None,
        "probability_horizon": None,
        "model_version": None,
        "calibrated": False,
        "decision_authority": False,
        "trade_authority": False,
    }
