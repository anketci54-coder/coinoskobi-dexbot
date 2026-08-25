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


def log_change(current, previous):
    current = _finite(current)
    previous = _finite(previous)

    if (
        current is None
        or previous is None
        or current <= 0
        or previous <= 0
    ):
        return None

    return math.log(
        current / previous
    )


def ewma_variance_step(
    log_return,
    *,
    previous_variance=None,
    decay=None,
):
    """
    One O(1) EWMA variance update.

    The decay parameter is deliberately mandatory at runtime.
    This module does not invent a RiskMetrics-style lambda before
    calibration on Coinoskobi data.
    """
    r = _finite(log_return)
    previous = _finite(previous_variance)
    lam = _finite(decay)

    if r is None:
        return {
            "state": "UNKNOWN",
            "ewma_variance": None,
            "ewma_volatility": None,
            "decay": lam,
            "decision_authority": False,
            "execution_authority": False,
        }

    if lam is None or not 0.0 < lam < 1.0:
        return {
            "state": "UNCALIBRATED",
            "ewma_variance": None,
            "ewma_volatility": None,
            "decay": lam,
            "decision_authority": False,
            "execution_authority": False,
        }

    if previous is not None and previous < 0:
        previous = None

    variance = (
        r * r
        if previous is None
        else (
            lam * previous
            + (1.0 - lam) * r * r
        )
    )

    return {
        "state": "READY",
        "ewma_variance": variance,
        "ewma_volatility": math.sqrt(variance),
        "decay": lam,
        "decision_authority": False,
        "execution_authority": False,
    }


def cusum_step(
    observation,
    *,
    previous_up=0.0,
    previous_down=0.0,
    reference=None,
    threshold=None,
):
    """
    Two-sided Page CUSUM update.

    reference and threshold must come from calibration / a target
    false-alarm policy. No magic thresholds live in this function.
    """
    x = _finite(observation)
    prev_up = _finite(previous_up)
    prev_down = _finite(previous_down)
    k = _finite(reference)
    h = _finite(threshold)

    if x is None:
        return {
            "state": "UNKNOWN",
            "up_cusum": None,
            "down_cusum": None,
            "change": "UNKNOWN",
            "decision_authority": False,
            "execution_authority": False,
        }

    if (
        k is None
        or h is None
        or k < 0
        or h <= 0
    ):
        return {
            "state": "UNCALIBRATED",
            "up_cusum": None,
            "down_cusum": None,
            "change": "UNKNOWN",
            "decision_authority": False,
            "execution_authority": False,
        }

    if prev_up is None or prev_up < 0:
        prev_up = 0.0

    if prev_down is None or prev_down < 0:
        prev_down = 0.0

    up = max(
        0.0,
        prev_up + x - k,
    )

    down = max(
        0.0,
        prev_down - x - k,
    )

    if down >= h and down > up:
        change = "DOWN_CHANGE"
    elif up >= h and up > down:
        change = "UP_CHANGE"
    else:
        change = "NO_CHANGE"

    return {
        "state": "READY",
        "up_cusum": up,
        "down_cusum": down,
        "change": change,
        "reference": k,
        "threshold": h,
        "decision_authority": False,
        "execution_authority": False,
    }
