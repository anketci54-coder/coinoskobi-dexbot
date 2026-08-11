def evaluate_wash_sybil(
    wallet_count=0,
    repeated_counterparty_ratio=0.0,
    circular_flow_ratio=0.0,
    coordination_score=0.0,
    independent_wallet_ratio=0.0,
    freshness="FRESH",
):
    if freshness != "FRESH":
        return _out("UNKNOWN", [], 0.0)

    wallets = _int(wallet_count)
    repeated = _score(repeated_counterparty_ratio)
    circular = _score(circular_flow_ratio)
    coordination = _score(coordination_score)
    independent = _score(independent_wallet_ratio)

    tags = []

    if repeated >= 0.70:
        tags.append("REPEATED_COUNTERPARTIES")

    if circular >= 0.70:
        tags.append("CIRCULAR_FLOW")

    if coordination >= 0.75:
        tags.append("COORDINATED_WALLETS")

    if wallets >= 5 and independent <= 0.30:
        tags.append("FAKE_MULTI_ACTOR_RISK")

    if wallets >= 5 and independent >= 0.70:
        tags.append("INDEPENDENT_MULTI_ACTOR_EVIDENCE")

    suspicion = (
        repeated * 0.30
        + circular * 0.30
        + coordination * 0.30
        + (1.0 - independent) * 0.10
    )

    suspicion = min(1.0, suspicion)

    strong_components = sum([
        repeated >= 0.70,
        circular >= 0.70,
        coordination >= 0.75,
    ])

    if strong_components >= 2 and suspicion >= 0.70:
        state = "STRONG_WASH_SYBIL_EVIDENCE"
    elif strong_components >= 1 and suspicion >= 0.50:
        state = "WASH_SYBIL_CANDIDATE"
    elif tags and "INDEPENDENT_MULTI_ACTOR_EVIDENCE" not in tags:
        state = "SUSPICIOUS_PARTICIPATION"
    elif "INDEPENDENT_MULTI_ACTOR_EVIDENCE" in tags:
        state = "INDEPENDENT_PARTICIPATION"
    else:
        state = "NONE"

    return _out(state, tags, suspicion)


def _out(state, tags, score):
    return {
        "state": state,
        "evidence_tags": tags,
        "suspicion_score": score,
        "wallet_count_is_participation_proof": False,
        "coordination_is_identity_proof": False,
        "trade_signal": False,
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
