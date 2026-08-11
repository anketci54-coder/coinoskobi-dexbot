SWAP_TOPIC = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
SYNC_TOPIC = "0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1"

DEFAULT_MAX_EVENTS = 256
DEFAULT_MAX_QUEUE = 1024
DEFAULT_STALE_SECONDS = 10


def build_ingestion_contract(
    pair,
    provider_class,
    transport,
    max_events=DEFAULT_MAX_EVENTS,
    max_queue=DEFAULT_MAX_QUEUE,
    stale_seconds=DEFAULT_STALE_SECONDS,
):
    transport = (transport or "").upper()

    if transport not in {"HTTP", "WSS"}:
        state = "UNSUPPORTED"
    elif not pair or not provider_class:
        state = "INVALID"
    else:
        state = "READY"

    return {
        "state": state,
        "pair": pair,
        "provider_class": provider_class,
        "transport": transport,
        "topics": [SWAP_TOPIC, SYNC_TOPIC],
        "max_events": max(1, int(max_events)),
        "max_queue": max(1, int(max_queue)),
        "stale_seconds": max(1, int(stale_seconds)),
        "bounded_read": True,
        "unbounded_getlogs_allowed": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def provider_capability(transport, connected, subscription_capable=False):
    transport = (transport or "").upper()

    if not connected:
        state = "DISCONNECTED"
    elif transport == "WSS" and subscription_capable:
        state = "SUBSCRIPTION_READY"
    elif transport == "HTTP":
        state = "BOUNDED_READ_ONLY"
    else:
        state = "CONNECTED_LIMITED"

    return {
        "state": state,
        "transport": transport,
        "connected": bool(connected),
        "subscription_capable": bool(subscription_capable),
        "unbounded_getlogs_allowed": False,
        "execution_authority": False,
    }
