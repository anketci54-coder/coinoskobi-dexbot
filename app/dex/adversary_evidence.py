def adversary_evidence(
    chain,
    actor_id,
    evidence_type,
    evidence_count=0,
    confidence=0.0,
    freshness="FRESH",
    provenance=None,
):
    chain = (chain or "").strip().lower()
    actor_id = (actor_id or "").strip().lower()
    evidence_type = (evidence_type or "").strip().upper()

    count = _int(evidence_count)
    conf = _score(confidence)

    if not chain or not actor_id or not evidence_type:
        state = "UNKNOWN"
    elif freshness != "FRESH":
        state = "UNKNOWN"
    elif count <= 0:
        state = "UNSUPPORTED"
    elif conf >= 0.85 and count >= 3:
        state = "STRONG_EVIDENCE"
    elif conf >= 0.50:
        state = "POSSIBLE_EVIDENCE"
    else:
        state = "WEAK_EVIDENCE"

    return {
        "state": state,
        "actor_key": f"{chain}:{actor_id}" if chain and actor_id else None,
        "chain": chain or None,
        "actor_id": actor_id or None,
        "evidence_type": evidence_type or None,
        "evidence_count": count,
        "confidence": conf,
        "freshness": freshness,
        "provenance": provenance,
        "suspicion_is_proof": False,
        "identity_proof": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _score(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0
