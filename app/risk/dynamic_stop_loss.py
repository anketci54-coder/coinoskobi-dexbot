import math


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def calculate_dynamic_sl(
    *,
    measured_sl_distance_pct=None,
    entry_price=None,
    stop_price=None,
    flow_momentum=None,
    flow_acceleration=None,
    liquidity_health=None,
    price_impact_health=None,
    trend_health=None,
    exit_pressure=None,
):
    """
    Compatibility-only measured SL adapter.

    This module does not create a stop from:
    - fixed percentages
    - semantic labels
    - scores
    - hand-tuned coefficients

    The mathematical stop must already exist.
    """

    distance = _number(
        measured_sl_distance_pct
    )
    source = None

    if distance is not None:
        if 0 < distance < 1:
            source = "MEASURED_DISTANCE"
        else:
            distance = None

    if distance is None:
        entry = _number(entry_price)
        stop = _number(stop_price)

        if (
            entry is not None
            and stop is not None
            and entry > 0
            and 0 < stop < entry
        ):
            distance = (
                entry - stop
            ) / entry
            source = "MEASURED_PRICES"

    if distance is None:
        return {
            "state": "UNKNOWN",
            "sl_distance_pct": None,
            "sl_multiplier": None,
            "source": None,
            "model": "MEASURED_SL_ONLY_V1",
            "semantic_inputs_used": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    return {
        "state": "MEASURED",
        "sl_distance_pct": distance,
        "sl_multiplier": 1.0 - distance,
        "source": source,
        "model": "MEASURED_SL_ONLY_V1",
        "semantic_inputs_used": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
