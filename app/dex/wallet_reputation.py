def evaluate_wallet_reputation(
    repeat_offender_count,
    coordination_score,
    concentration_score,
    hard_evidence=False,
    soft_age=0,
    freshness="FRESH",
):
    if freshness != "FRESH":
        return _out("UNKNOWN", 0.0, bool(hard_evidence), [])

    repeat = max(0, int(repeat_offender_count or 0))
    coord = _score(coordination_score)
    concentration = _score(concentration_score)
    age = max(0, int(soft_age or 0))

    tags = []

    if repeat >= 3:
        tags.append("REPEAT_OFFENDER")

    if coord >= 0.80:
        tags.append("COORDINATION_RISK")

    if concentration >= 0.80:
        tags.append("CONCENTRATION_RISK")

    soft = min(
        1.0,
        repeat * 0.15
        + coord * 0.45
        + concentration * 0.40,
    )

    if not hard_evidence:
        soft *= max(0.0, 1.0 - min(age, 100) / 100)

    if hard_evidence:
        state = "HARD_RISK_EVIDENCE"
    elif soft >= 0.75:
        state = "HIGH_RISK"
    elif soft >= 0.40:
        state = "ELEVATED_RISK"
    elif tags:
        state = "WATCH"
    else:
        state = "LOW_RISK"

    return _out(state, soft, bool(hard_evidence), tags)


def _out(state, score, hard, tags):
    return {
        "state": state,
        "risk_score": score,
        "hard_evidence": hard,
        "tags": tags,
        "hard_evidence_decays": False,
        "trade_signal": False,
        "decision_authority": False,
        "execution_authority": False,
    }


def _score(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0
