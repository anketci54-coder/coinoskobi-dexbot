_PROVIDER_FAILURES = {
    "TIMEOUT",
    "RATE_LIMIT",
    "QUOTA",
    "FORBIDDEN",
    "CONNECTION",
    "SUBSCRIPTION",
}


def classify_provider_failure(error):
    text = str(error or "").lower()

    if not text:
        return "UNKNOWN"

    if (
        "429" in text
        or "too many requests" in text
        or "rate limit" in text
        or "limit exceeded" in text
        or "-32005" in text
    ):
        return "RATE_LIMIT"

    if any(
        marker in text
        for marker in (
            "quota",
            "credits exhausted",
            "credit exhausted",
            "compute units",
            "capacity exceeded",
            "request limit",
            "plan limit",
        )
    ):
        return "QUOTA"

    if "403" in text or "forbidden" in text:
        return "FORBIDDEN"

    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"

    if (
        "connection" in text
        or "disconnected" in text
        or "connection reset" in text
    ):
        return "CONNECTION"

    if "subscription" in text:
        return "SUBSCRIPTION"

    return "OTHER"


def _failure_name(error):
    normalized = str(
        error or ""
    ).strip().upper()

    if normalized in _PROVIDER_FAILURES:
        return normalized

    return classify_provider_failure(
        error
    )


def provider_cooldown_seconds(
    error,
    *,
    quota_seconds=300.0,
    transient_seconds=15.0,
):
    failure = _failure_name(error)

    if failure in {
        "RATE_LIMIT",
        "QUOTA",
        "FORBIDDEN",
    }:
        return max(
            1.0,
            float(quota_seconds),
        )

    if failure in {
        "TIMEOUT",
        "CONNECTION",
        "SUBSCRIPTION",
    }:
        return max(
            1.0,
            float(transient_seconds),
        )

    return 0.0
