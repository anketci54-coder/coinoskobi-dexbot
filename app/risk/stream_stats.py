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


def empirical_expected_shortfall(
    returns,
    *,
    alpha=None,
):
    """
    Historical Expected Shortfall / CVaR on observed returns.

    alpha is deliberately mandatory. The function does not assume a
    95% or 99% confidence level. Loss is represented as a positive
    fraction, while the tail return remains in return space.
    """
    confidence = _finite(alpha)

    if confidence is None or not 0.0 <= confidence < 1.0:
        return {
            "state": "UNCALIBRATED",
            "alpha": confidence,
            "sample_count": 0,
            "tail_count": 0,
            "var_return": None,
            "expected_shortfall_return": None,
            "expected_shortfall_loss_fraction": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    observed = []

    for value in returns or ():
        number = _finite(value)
        if number is not None:
            observed.append(number)

    if not observed:
        return {
            "state": "UNKNOWN",
            "alpha": confidence,
            "sample_count": 0,
            "tail_count": 0,
            "var_return": None,
            "expected_shortfall_return": None,
            "expected_shortfall_loss_fraction": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    ordered = sorted(observed)
    tail_probability = 1.0 - confidence
    tail_count = max(
        1,
        int(math.ceil(
            len(ordered) * tail_probability
        )),
    )

    tail = ordered[:tail_count]
    var_return = tail[-1]
    es_return = sum(tail) / len(tail)
    loss_fraction = max(
        0.0,
        -math.expm1(es_return),
    )

    return {
        "state": "READY",
        "model": "HISTORICAL_EXPECTED_SHORTFALL",
        "alpha": confidence,
        "sample_count": len(ordered),
        "tail_count": len(tail),
        "var_return": var_return,
        "expected_shortfall_return": es_return,
        "expected_shortfall_loss_fraction": loss_fraction,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _adjacent_log_changes(
    observations,
    field,
):
    changes = []
    previous = None

    for row in observations or ():
        if not isinstance(row, dict):
            previous = None
            continue

        value = _finite(
            row.get(field)
        )

        if value is None or value <= 0:
            previous = None
            continue

        if previous is not None:
            changes.append(
                math.log(
                    value / previous
                )
            )

        previous = value

    return changes


def calibrate_ewma_decay(
    log_returns,
):
    """
    Select EWMA decay from observed returns.

    Candidate resolution is derived from sample count:
        lambda = i / n, i=1..n-1

    The selected lambda minimizes one-step squared
    variance forecast error. No fixed RiskMetrics
    lambda is embedded.
    """
    values = []

    for value in log_returns or ():
        number = _finite(value)

        if number is not None:
            values.append(number)

    n = len(values)

    if n < 3:
        return {
            "state": "INSUFFICIENT_DATA",
            "decay": None,
            "sample_count": n,
            "forecast_count": max(0, n - 1),
            "loss": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    if not any(
        value != 0.0
        for value in values
    ):
        return {
            "state": "UNINFORMATIVE",
            "decay": None,
            "sample_count": n,
            "forecast_count": n - 1,
            "loss": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    best = None

    for i in range(1, n):
        decay = i / n

        variance = (
            values[0]
            * values[0]
        )

        squared_errors = []

        for value in values[1:]:
            realized_variance = (
                value * value
            )

            error = (
                realized_variance
                - variance
            )

            squared_errors.append(
                error * error
            )

            variance = (
                decay * variance
                + (1.0 - decay)
                * realized_variance
            )

        loss = (
            sum(squared_errors)
            / len(squared_errors)
        )

        candidate = (
            loss,
            -decay,
            decay,
        )

        if (
            best is None
            or candidate < best
        ):
            best = candidate

    return {
        "state": "READY",
        "model": (
            "ONE_STEP_EWMA_VARIANCE_CALIBRATION"
        ),
        "decay": best[2],
        "sample_count": n,
        "forecast_count": n - 1,
        "loss": best[0],
        "candidate_count": n - 1,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def calibrate_cusum(
    log_changes,
):
    """
    Robust two-sided CUSUM calibration.

    reference:
        median absolute observed log change

    threshold:
        the smallest floating-point value strictly
        above the maximum in-sample CUSUM excursion.

    Therefore the calibration window does not
    trigger itself and no fixed alarm percentage
    or multiplier is invented.
    """
    values = []

    for value in log_changes or ():
        number = _finite(value)

        if number is not None:
            values.append(number)

    n = len(values)

    if n < 2:
        return {
            "state": "INSUFFICIENT_DATA",
            "reference": None,
            "threshold": None,
            "sample_count": n,
            "decision_authority": False,
            "execution_authority": False,
        }

    absolute = sorted(
        abs(value)
        for value in values
    )

    middle = n // 2

    if n % 2:
        reference = absolute[middle]
    else:
        reference = (
            absolute[middle - 1]
            + absolute[middle]
        ) / 2.0

    up = 0.0
    down = 0.0
    max_excursion = 0.0

    for value in values:
        up = max(
            0.0,
            up + value - reference,
        )

        down = max(
            0.0,
            down - value - reference,
        )

        max_excursion = max(
            max_excursion,
            up,
            down,
        )

    if max_excursion <= 0:
        return {
            "state": "UNINFORMATIVE",
            "reference": reference,
            "threshold": None,
            "sample_count": n,
            "max_in_sample_excursion": (
                max_excursion
            ),
            "decision_authority": False,
            "execution_authority": False,
        }

    threshold = math.nextafter(
        max_excursion,
        math.inf,
    )

    return {
        "state": "READY",
        "model": (
            "ROBUST_EMPIRICAL_CUSUM_CALIBRATION"
        ),
        "reference": reference,
        "threshold": threshold,
        "sample_count": n,
        "max_in_sample_excursion": (
            max_excursion
        ),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def calibrate_stream_math(
    observations,
):
    """
    Produce pool/source-specific streaming calibration
    from raw market observations.

    Mixed chain/dex/pool/source evidence is rejected.
    """
    rows = [
        dict(row)
        for row in (observations or ())
        if isinstance(row, dict)
    ]

    identities = set()

    for row in rows:
        identity = tuple(
            str(
                row.get(field)
                or ""
            ).strip().lower()
            for field in (
                "chain",
                "dex",
                "pool",
                "source",
            )
        )

        if all(identity):
            identities.add(identity)

    if len(identities) > 1:
        return {
            "state": "IDENTITY_MIXED",
            "identity": None,
            "observation_count": len(rows),
            "calibration": {},
            "decision_authority": False,
            "execution_authority": False,
        }

    identity = (
        next(iter(identities))
        if identities
        else None
    )

    if identity is None:
        return {
            "state": "IDENTITY_UNKNOWN",
            "identity": None,
            "observation_count": len(rows),
            "calibration": {},
            "decision_authority": False,
            "execution_authority": False,
        }

    price_returns = (
        _adjacent_log_changes(
            rows,
            "price_usd",
        )
    )

    liquidity_changes = (
        _adjacent_log_changes(
            rows,
            "liquidity_usd",
        )
    )

    ewma = calibrate_ewma_decay(
        price_returns
    )

    cusum = calibrate_cusum(
        liquidity_changes
    )

    calibration = {}

    if ewma.get("state") == "READY":
        calibration["ewma_decay"] = (
            ewma["decay"]
        )

    if cusum.get("state") == "READY":
        calibration[
            "cusum_reference"
        ] = cusum["reference"]

        calibration[
            "cusum_threshold"
        ] = cusum["threshold"]

    ready_count = sum(
        (
            ewma.get("state") == "READY",
            cusum.get("state") == "READY",
        )
    )

    if ready_count == 2:
        state = "READY"
    elif ready_count == 1:
        state = "PARTIAL"
    else:
        state = "INSUFFICIENT_DATA"

    return {
        "state": state,
        "model_version": (
            "STREAM_MATH_CALIBRATION_V1"
        ),
        "identity": {
            "chain": identity[0],
            "dex": identity[1],
            "pool": identity[2],
            "source": identity[3],
        },
        "observation_count": len(rows),
        "price_return_count": len(
            price_returns
        ),
        "liquidity_change_count": len(
            liquidity_changes
        ),
        "ewma": ewma,
        "liquidity_cusum": cusum,
        "calibration": calibration,
        "observation_step_model": (
            "SOURCE_ISOLATED_SCANNER_SEQUENCE"
        ),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
