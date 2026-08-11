def build_entity_link(
    wallet_id,
    entity_id,
    evidence_count,
    confidence,
    ambiguous=False,
    source_fresh=True,
):
    if not wallet_id or not entity_id:
        state = "UNKNOWN"
    elif ambiguous or not source_fresh:
        state = "UNKNOWN"
    elif evidence_count <= 0:
        state = "UNSUPPORTED"
    elif confidence >= 0.90 and evidence_count >= 3:
        state = "STRONG_LINK"
    elif confidence >= 0.60:
        state = "POSSIBLE_LINK"
    else:
        state = "WEAK_LINK"

    return {
        "state": state,
        "wallet_id": wallet_id,
        "entity_id": entity_id,
        "evidence_count": max(0, int(evidence_count or 0)),
        "confidence": _confidence(confidence),
        "ambiguous": bool(ambiguous),
        "source_fresh": bool(source_fresh),
        "auto_merge": False,
        "identity_proof": False,
        "decision_authority": False,
        "execution_authority": False,
    }


def same_entity_candidate(wallet_a, wallet_b):
    a_chain, a_addr = _parts(wallet_a)
    b_chain, b_addr = _parts(wallet_b)

    if not a_chain or not b_chain:
        return {
            "candidate": False,
            "reason": "UNKNOWN_IDENTITY",
            "auto_merge": False,
        }

    if a_chain != b_chain:
        return {
            "candidate": False,
            "reason": "CROSS_CHAIN",
            "auto_merge": False,
        }

    if a_addr != b_addr:
        return {
            "candidate": False,
            "reason": "DIFFERENT_ADDRESS",
            "auto_merge": False,
        }

    return {
        "candidate": True,
        "reason": "SAME_CHAIN_SAME_ADDRESS",
        "auto_merge": False,
    }


def _parts(wallet_id):
    if not wallet_id or ":" not in wallet_id:
        return None, None
    chain, address = wallet_id.split(":", 1)
    return chain.lower(), address.lower()


def _confidence(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
