def classify_provider_failure(error):
    text = str(error or "").lower()

    if not text:
        return "UNKNOWN"

    if "timeout" in text:
        return "TIMEOUT"

    if "limit exceeded" in text or "-32005" in text:
        return "RATE_LIMIT"

    if "connection" in text or "disconnected" in text:
        return "CONNECTION"

    if "subscription" in text:
        return "SUBSCRIPTION"

    return "OTHER"


def choose_provider(primary, fallback=None):
    p = primary or {}
    f = fallback or {}

    if p.get("healthy"):
        return _out("PRIMARY", p.get("name"))

    if f.get("healthy"):
        return _out("FALLBACK", f.get("name"))

    return _out("UNAVAILABLE", None)


def failover_allowed(
    attempts,
    max_failovers=1,
    fallback_available=True,
):
    attempts = max(0, int(attempts))
    allowed = bool(
        fallback_available
        and attempts < max(1, int(max_failovers))
    )

    return {
        "allowed": allowed,
        "attempts": attempts,
        "max_failovers": max(1, int(max_failovers)),
        "bounded": True,
        "decision_authority": False,
        "execution_authority": False,
    }


def _out(state, provider):
    return {
        "state": state,
        "provider": provider,
        "paid_provider_required": False,
        "secret_logging_allowed": False,
        "decision_authority": False,
        "execution_authority": False,
    }
