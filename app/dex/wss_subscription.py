from app.dex.native_ingestion import SWAP_TOPIC, SYNC_TOPIC

TOPICS = {
    SWAP_TOPIC: "SWAP",
    SYNC_TOPIC: "SYNC",
}


def subscribe_request(pair, request_id=1, max_addresses=256):
    if isinstance(pair, str):
        addresses = [pair.strip()]
    else:
        try:
            addresses = [
                str(value).strip()
                for value in pair
                if str(value).strip()
            ]
        except TypeError:
            addresses = []

    addresses = list(dict.fromkeys(addresses))

    if not addresses or len(addresses) > int(max_addresses):
        return {"state": "INVALID"}

    address_filter = (
        addresses[0]
        if len(addresses) == 1
        else addresses
    )

    return {
        "state": "READY",
        "request": {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "eth_subscribe",
            "params": [
                "logs",
                {
                    "address": address_filter,
                    "topics": [[SWAP_TOPIC, SYNC_TOPIC]],
                },
            ],
        },
        "address_count": len(addresses),
        "bounded": True,
        "execution_authority": False,
    }


def unsubscribe_request(subscription_id, request_id=2):
    if not subscription_id:
        return {"state": "INVALID"}

    return {
        "state": "READY",
        "request": {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "eth_unsubscribe",
            "params": [subscription_id],
        },
        "execution_authority": False,
    }


def normalize_wss_event(message):
    msg = message or {}

    if msg.get("method") != "eth_subscription":
        return _reject("NOT_SUBSCRIPTION")

    params = msg.get("params") or {}
    log = params.get("result") or {}
    topics = log.get("topics") or []

    if not params.get("subscription"):
        return _reject("MISSING_SUBSCRIPTION")

    topic0 = topics[0].lower() if topics else None
    event_type = TOPICS.get(topic0)

    if not event_type:
        return _reject("UNSUPPORTED_TOPIC")

    tx = log.get("transactionHash")
    idx = log.get("logIndex")

    if not tx or idx is None:
        return _reject("MISSING_IDENTITY")

    return {
        "state": "NORMALIZED",
        "event_type": event_type,
        "subscription_id": params["subscription"],
        "event_identity": f"{tx}:{idx}",
        "transaction_hash": tx,
        "log_index": idx,
        "block_number": log.get("blockNumber"),
        "removed": bool(log.get("removed", False)),
        "address": (
            str(log.get("address") or "")
            .strip()
            .lower()
            or None
        ),
        "data": log.get("data"),
        "topics": list(topics),
        "decision_authority": False,
        "execution_authority": False,
    }


def _reject(reason):
    return {
        "state": "REJECTED",
        "reason": reason,
        "decision_authority": False,
        "execution_authority": False,
    }
