def reconnect_delay(attempt, base=1.0, maximum=30.0):
    attempt = max(0, int(attempt))
    return min(float(maximum), float(base) * (2 ** attempt))


def connection_health(
    connected,
    seconds_since_event,
    reconnect_count=0,
    stale_seconds=10,
    max_reconnects=5,
):
    reconnect_count = max(0, int(reconnect_count))

    if connected:
        if seconds_since_event is None:
            state = "CONNECTED"
        elif seconds_since_event > stale_seconds:
            state = "STALE"
        else:
            state = "CONNECTED"
    elif reconnect_count >= max_reconnects:
        state = "DISCONNECTED"
    else:
        state = "DEGRADED"

    return {
        "state": state,
        "connected": bool(connected),
        "reconnect_count": reconnect_count,
        "reconnect_allowed": (
            not connected and reconnect_count < max_reconnects
        ),
        "stale": state == "STALE",
        "decision_authority": False,
        "execution_authority": False,
    }
