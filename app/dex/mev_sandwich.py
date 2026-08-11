def evaluate_sandwich_evidence(
    same_block,
    frontrun_before_victim,
    backrun_after_victim,
    victim_price_impact,
    repeated_pattern_count=0,
    gas_priority_relation=False,
    freshness="FRESH",
):
    if freshness != "FRESH":
        return _out("UNKNOWN", [], 0.0)

    repeated = _int(repeated_pattern_count)
    impact = _num(victim_price_impact)

    evidence = []

    if same_block:
        evidence.append("SAME_BLOCK")

    if frontrun_before_victim:
        evidence.append("FRONTRUN_ORDERING")

    if backrun_after_victim:
        evidence.append("BACKRUN_ORDERING")

    if impact > 0:
        evidence.append("VICTIM_PRICE_IMPACT")

    if gas_priority_relation:
        evidence.append("GAS_PRIORITY_RELATION")

    if repeated >= 2:
        evidence.append("REPEATED_PATTERN")

    core_sequence = (
        same_block
        and frontrun_before_victim
        and backrun_after_victim
    )

    strong = (
        core_sequence
        and impact > 0
        and repeated >= 2
    )

    possible = (
        core_sequence
        and impact > 0
    )

    if strong:
        state = "SANDWICH_STRONG_EVIDENCE"
    elif possible:
        state = "SANDWICH_CANDIDATE"
    elif core_sequence:
        state = "MEV_LIKE_ORDERING"
    elif evidence:
        state = "INSUFFICIENT_EVIDENCE"
    else:
        state = "NONE"

    confidence = _confidence(
        core_sequence=core_sequence,
        impact=impact,
        repeated=repeated,
        gas_relation=gas_priority_relation,
    )

    return _out(state, evidence, confidence)


def classify_mev_context(
    sandwich_state,
    arbitrage_like=False,
):
    if sandwich_state == "UNKNOWN":
        state = "UNKNOWN"
    elif arbitrage_like and sandwich_state in {
        "NONE",
        "INSUFFICIENT_EVIDENCE",
        "MEV_LIKE_ORDERING",
    }:
        state = "NORMAL_ARBITRAGE_POSSIBLE"
    elif sandwich_state == "SANDWICH_STRONG_EVIDENCE":
        state = "HIGH_MEV_RISK"
    elif sandwich_state == "SANDWICH_CANDIDATE":
        state = "ELEVATED_MEV_RISK"
    else:
        state = "LOW_OR_UNRESOLVED_MEV_RISK"

    return {
        "state": state,
        "normal_arbitrage_is_sandwich": False,
        "trade_signal": False,
        "decision_authority": False,
        "execution_authority": False,
    }


def _confidence(
    core_sequence,
    impact,
    repeated,
    gas_relation,
):
    score = 0.0

    if core_sequence:
        score += 0.45
    if impact > 0:
        score += 0.20
    if repeated >= 2:
        score += 0.25
    if gas_relation:
        score += 0.10

    return min(1.0, score)


def _out(state, evidence, confidence):
    return {
        "state": state,
        "evidence": evidence,
        "confidence": confidence,
        "single_event_is_proof": False,
        "normal_arbitrage_is_sandwich": False,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _num(v):
    try:
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 0.0


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0
