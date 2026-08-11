def evaluate_sniper_pumpdump(
    early_buy_count=0,
    coordinated_early_buy_score=0.0,
    accumulation_concentration=0.0,
    distribution_concentration=0.0,
    synchronized_dump_score=0.0,
    repeat_pumpdump_count=0,
    freshness="FRESH",
):
    if freshness != "FRESH":
        return _out("UNKNOWN", [], 0.0)

    early = _int(early_buy_count)
    coordination = _score(coordinated_early_buy_score)
    accumulation = _score(accumulation_concentration)
    distribution = _score(distribution_concentration)
    sync_dump = _score(synchronized_dump_score)
    repeat = _int(repeat_pumpdump_count)

    tags = []

    if early > 0:
        tags.append("EARLY_BUY_ACTIVITY")

    if coordination >= 0.75:
        tags.append("COORDINATED_EARLY_BUYS")

    if accumulation >= 0.75:
        tags.append("CONCENTRATED_ACCUMULATION")

    if distribution >= 0.75:
        tags.append("CONCENTRATED_DISTRIBUTION")

    if sync_dump >= 0.75:
        tags.append("SYNCHRONIZED_DUMP")

    if repeat >= 2:
        tags.append("REPEAT_PUMPDUMP_ASSOCIATION")

    score = min(
        1.0,
        coordination * 0.25
        + accumulation * 0.20
        + distribution * 0.20
        + sync_dump * 0.25
        + min(repeat, 3) * 0.10,
    )

    malicious_components = sum([
        coordination >= 0.75,
        distribution >= 0.75,
        sync_dump >= 0.75,
        repeat >= 2,
    ])

    if malicious_components >= 3 and score >= 0.75:
        state = "STRONG_PUMPDUMP_EVIDENCE"
    elif malicious_components >= 2 and score >= 0.55:
        state = "PUMPDUMP_CANDIDATE"
    elif early > 0:
        state = "SNIPER_ACTIVITY"
    else:
        state = "NONE"

    return _out(state, tags, score)


def _out(state, tags, score):
    return {
        "state": state,
        "evidence_tags": tags,
        "risk_score": score,
        "sniper_is_malicious_proof": False,
        "early_buy_is_attack_proof": False,
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
