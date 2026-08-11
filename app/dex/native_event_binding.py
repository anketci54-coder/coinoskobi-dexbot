def bind_native_event_context(
    normalized_event,
    integrity,
    buffer_health,
    subscription_health,
):
    event = normalized_event or {}
    integ = integrity or {}
    buffer = buffer_health or {}
    health = subscription_health or {}

    ready = (
        event.get("state") == "NORMALIZED"
        and integ.get("state") == "ACCEPTED"
        and health.get("state") == "CONNECTED"
        and buffer.get("state") in {"HEALTHY", "PRESSURED"}
    )

    return {
        "native_context_ready": ready,
        "event_type": event.get("event_type"),
        "event_identity": event.get("event_identity"),
        "transaction_hash": event.get("transaction_hash"),
        "log_index": event.get("log_index"),
        "block_number": event.get("block_number"),
        "removed": event.get("removed", False),
        "integrity_state": integ.get("state", "UNKNOWN"),
        "buffer_state": buffer.get("state", "UNKNOWN"),
        "subscription_state": health.get("state", "UNKNOWN"),
        "provider_class": health.get("provider_class"),
        "fresh": health.get("fresh", False),
        "phase5_input_allowed": ready,
        "phase7_input_allowed": ready,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
