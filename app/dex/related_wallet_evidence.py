def related_wallet_evidence(
    wallet_a,
    wallet_b,
    *,
    direct_funding=False,
    repeated_transfers=0,
    common_funder=False,
    coordinated_entries=0,
    coordinated_exits=0,
    source_fresh=True,
):
    """Score cross-wallet relationship evidence without auto-merging identity."""
    a = _id(wallet_a)
    b = _id(wallet_b)

    if not a or not b or a == b or not source_fresh:
        return _out("UNKNOWN", a, b, 0.0, 0)

    if _chain(a) != _chain(b):
        return _out("CROSS_CHAIN", a, b, 0.0, 0)

    transfers = _count(repeated_transfers)
    entries = _count(coordinated_entries)
    exits = _count(coordinated_exits)

    score = 0.0
    evidence_count = 0
    tags = []

    if direct_funding:
        score += 0.40
        evidence_count += 1
        tags.append("DIRECT_FUNDING")
    if transfers >= 2:
        score += min(0.25, transfers * 0.05)
        evidence_count += 1
        tags.append("REPEATED_TRANSFERS")
    if common_funder:
        score += 0.15
        evidence_count += 1
        tags.append("COMMON_FUNDER")
    if entries >= 3:
        score += min(0.15, entries * 0.03)
        evidence_count += 1
        tags.append("COORDINATED_ENTRIES")
    if exits >= 3:
        score += min(0.10, exits * 0.02)
        evidence_count += 1
        tags.append("COORDINATED_EXITS")

    score = min(1.0, score)

    # Relationship is evidence, never ownership proof. Strong requires
    # multiple independent evidence classes to reduce false linkage.
    if evidence_count >= 3 and score >= 0.75:
        state = "STRONG_RELATIONSHIP"
    elif evidence_count >= 2 and score >= 0.45:
        state = "POSSIBLE_RELATIONSHIP"
    elif evidence_count:
        state = "WEAK_RELATIONSHIP"
    else:
        state = "UNSUPPORTED"

    return _out(state, a, b, score, evidence_count, tags)


def _id(value):
    value = str(value or "").strip().lower()
    return value or None


def _chain(wallet_id):
    return wallet_id.split(":", 1)[0] if ":" in wallet_id else None


def _count(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _out(state, wallet_a, wallet_b, confidence, evidence_count, tags=None):
    return {
        "state": state,
        "wallet_a": wallet_a,
        "wallet_b": wallet_b,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "tags": list(tags or []),
        "identity_proof": False,
        "ownership_claim": False,
        "auto_merge": False,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
