def build_subscription_health(
    connection_state,
    provider_class,
    seconds_since_event=None,
    reconnect_count=0,
    duplicate_count=0,
    dropped_count=0,
    rejected_count=0,
    stale_seconds=10,
):
    reconnect_count = max(0, int(reconnect_count))
    duplicate_count = max(0, int(duplicate_count))
    dropped_count = max(0, int(dropped_count))
    rejected_count = max(0, int(rejected_count))

    if connection_state == "DISCONNECTED":
        state = "DISCONNECTED"
    elif connection_state == "DEGRADED":
        state = "DEGRADED"
    elif seconds_since_event is not None and seconds_since_event > stale_seconds:
        state = "STALE"
    elif connection_state == "CONNECTED":
        state = "CONNECTED"
    else:
        state = "UNKNOWN"

    return {
        "state": state,
        "provider_class": provider_class,
        "seconds_since_event": seconds_since_event,
        "reconnect_count": reconnect_count,
        "duplicate_count": duplicate_count,
        "dropped_count": dropped_count,
        "rejected_count": rejected_count,
        "fresh": state == "CONNECTED",
        "degraded": state == "DEGRADED",
        "stale": state == "STALE",
        "decision_authority": False,
        "execution_authority": False,
    }
