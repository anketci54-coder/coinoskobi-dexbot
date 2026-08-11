def evaluate_adversary_reputation(
    mev_state="LOW_OR_UNRESOLVED_MEV_RISK",
    scam_state="NONE",
    wash_state="NONE",
    pumpdump_state="NONE",
    repeat_offender_count=0,
    hard_evidence=False,
    soft_age=0,
    conflicting_evidence=False,
    freshness="FRESH",
):
    if freshness != "FRESH":
        return _out(
            state="UNKNOWN",
            score=0.0,
            hard=bool(hard_evidence),
            tags=[],
        )

    repeat = _int(repeat_offender_count)
    age = _int(soft_age)

    tags = []
    score = 0.0

    # MEV
    if mev_state == "HIGH_MEV_RISK":
        tags.append("HIGH_MEV_RISK")
        score += 0.30
    elif mev_state == "ELEVATED_MEV_RISK":
        tags.append("ELEVATED_MEV_RISK")
        score += 0.18

    # Scam / rug
    if scam_state == "STRONG_SCAM_RUG_EVIDENCE":
        tags.append("STRONG_SCAM_RUG_EVIDENCE")
        score += 0.35
    elif scam_state == "SCAM_RUG_CANDIDATE":
        tags.append("SCAM_RUG_CANDIDATE")
        score += 0.20
    elif scam_state == "SUSPICIOUS_ASSOCIATION":
        tags.append("SCAM_RUG_ASSOCIATION")
        score += 0.08

    # Wash / sybil
    if wash_state == "STRONG_WASH_SYBIL_EVIDENCE":
        tags.append("STRONG_WASH_SYBIL_EVIDENCE")
        score += 0.25
    elif wash_state == "WASH_SYBIL_CANDIDATE":
        tags.append("WASH_SYBIL_CANDIDATE")
        score += 0.15
    elif wash_state == "SUSPICIOUS_PARTICIPATION":
        tags.append("SUSPICIOUS_PARTICIPATION")
        score += 0.07

    # Pump / dump
    if pumpdump_state == "STRONG_PUMPDUMP_EVIDENCE":
        tags.append("STRONG_PUMPDUMP_EVIDENCE")
        score += 0.30
    elif pumpdump_state == "PUMPDUMP_CANDIDATE":
        tags.append("PUMPDUMP_CANDIDATE")
        score += 0.18
    elif pumpdump_state == "SNIPER_ACTIVITY":
        tags.append("SNIPER_ACTIVITY")
        score += 0.03

    # Repeat offender
    if repeat >= 3:
        tags.append("REPEAT_OFFENDER")
        score += min(0.25, repeat * 0.05)

    score = min(1.0, score)

    # Soft suspicion decays over time.
    if not hard_evidence:
        decay = max(0.0, 1.0 - min(age, 100) / 100.0)
        score *= decay

    if conflicting_evidence and not hard_evidence:
        state = "UNRESOLVED_CONFLICT"
    elif hard_evidence:
        state = "HARD_ADVERSARY_EVIDENCE"
    elif score >= 0.75:
        state = "HIGH_RISK"
    elif score >= 0.40:
        state = "ELEVATED_RISK"
    elif score > 0:
        state = "WATCH"
    else:
        state = "LOW_RISK"

    return _out(
        state=state,
        score=score,
        hard=bool(hard_evidence),
        tags=tags,
    )


def _out(state, score, hard, tags):
    return {
        "state": state,
        "risk_score": score,
        "hard_evidence": hard,
        "evidence_tags": tags,
        "hard_evidence_decays": False,
        "soft_suspicion_can_decay": True,
        "conflict_can_force_safe_downgrade": True,
        "trade_permission": False,
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
