def normalize_wallet(chain, address):
    chain = (chain or "").strip().lower()
    address = (address or "").strip().lower()

    if not chain or not address:
        return {
            "state": "UNKNOWN",
            "wallet_id": None,
            "chain": chain or None,
            "address": address or None,
            "identity_guessing": False,
        }

    return {
        "state": "READY",
        "wallet_id": f"{chain}:{address}",
        "chain": chain,
        "address": address,
        "identity_guessing": False,
    }


def wallet_evidence(
    chain,
    address,
    inbound_value=0,
    outbound_value=0,
    buy_count=0,
    sell_count=0,
    freshness="FRESH",
):
    wallet = normalize_wallet(chain, address)

    if wallet["state"] != "READY" or freshness != "FRESH":
        state = "UNKNOWN"
    else:
        state = "READY"

    inbound = _num(inbound_value)
    outbound = _num(outbound_value)
    buys = _int(buy_count)
    sells = _int(sell_count)

    return {
        "state": state,
        "wallet_id": wallet["wallet_id"],
        "chain": wallet["chain"],
        "address": wallet["address"],
        "inbound_value": inbound,
        "outbound_value": outbound,
        "net_flow": inbound - outbound,
        "buy_count": buys,
        "sell_count": sells,
        "participation_count": buys + sells,
        "freshness": freshness,
        "identity_guessing": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _num(value):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
