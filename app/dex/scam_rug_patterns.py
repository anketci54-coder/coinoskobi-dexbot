def evaluate_scam_rug_patterns(
    repeat_rug_count=0,
    liquidity_removal_count=0,
    suspicious_deployer_links=0,
    suspicious_funder_links=0,
    honeypot_associations=0,
    repeat_launch_count=0,
    confidence=0.0,
    freshness="FRESH",
):
    if freshness != "FRESH":
        return _out("UNKNOWN", [], 0.0)

    repeat_rug = _int(repeat_rug_count)
    liquidity = _int(liquidity_removal_count)
    deployer = _int(suspicious_deployer_links)
    funder = _int(suspicious_funder_links)
    honeypot = _int(honeypot_associations)
    launches = _int(repeat_launch_count)
    conf = _score(confidence)

    tags = []

    if repeat_rug > 0:
        tags.append("RUG_ASSOCIATION")

    if liquidity > 0:
        tags.append("LIQUIDITY_REMOVAL_EVIDENCE")

    if deployer > 0:
        tags.append("SUSPICIOUS_DEPLOYER_ASSOCIATION")

    if funder > 0:
        tags.append("SUSPICIOUS_FUNDER_ASSOCIATION")

    if honeypot > 0:
        tags.append("HONEYPOT_ASSOCIATION")

    if launches >= 3:
        tags.append("REPEAT_LAUNCH_PATTERN")

    weighted = (
        min(repeat_rug, 3) * 0.22
        + min(liquidity, 3) * 0.18
        + min(honeypot, 3) * 0.20
        + min(deployer, 3) * 0.10
        + min(funder, 3) * 0.08
        + min(launches, 5) * 0.04
    )

    evidence_score = min(1.0, weighted * conf)

    hard_count = repeat_rug + liquidity + honeypot

    if hard_count >= 3 and conf >= 0.85:
        state = "STRONG_SCAM_RUG_EVIDENCE"
    elif hard_count >= 1 and conf >= 0.60:
        state = "SCAM_RUG_CANDIDATE"
    elif tags:
        state = "SUSPICIOUS_ASSOCIATION"
    else:
        state = "NONE"

    return _out(state, tags, evidence_score)


def _out(state, tags, score):
    return {
        "state": state,
        "evidence_tags": tags,
        "evidence_score": score,
        "single_association_is_proof": False,
        "same_funder_is_same_actor": False,
        "identity_proof": False,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def _score(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0
