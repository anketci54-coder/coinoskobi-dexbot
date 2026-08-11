def evaluate_flow_agreement(
    direction,
    confirmation,
    participation,
    wallet_flow,
    liquidity,
    price_impact,
):
    values = {
        direction,
        confirmation,
        participation,
        wallet_flow,
        liquidity,
        price_impact,
    }

    if "UNKNOWN" in values or None in values:
        state = "UNKNOWN"
        score = None
    else:
        score = 0

        if confirmation == "CONFIRMED":
            score += 2
        elif confirmation == "PARTIAL_CONFIRMATION":
            score += 1
        elif confirmation == "CONFLICT":
            score -= 2

        if participation == "DIVERSE":
            score += 1
        elif participation == "CONCENTRATED":
            score -= 1

        if wallet_flow == "DIVERSE":
            score += 1
        elif wallet_flow in {"CONCENTRATED", "SINGLE_ACTOR_SPIKE"}:
            score -= 1

        if liquidity in {"STABLE", "IMPROVING", "STABLE_OR_UNKNOWN"}:
            score += 1
        elif liquidity in {"DETERIORATING", "DETERIORATING_FAST", "CRITICAL"}:
            score -= 1

        if price_impact == "HEALTHY":
            score += 1
        elif price_impact in {"HIGH", "UNHEALTHY", "CRITICAL"}:
            score -= 1

        if score >= 6:
            state = "STRONG_AGREEMENT"
        elif score >= 4:
            state = "AGREEMENT"
        elif score >= 1:
            state = "PARTIAL_AGREEMENT"
        else:
            state = "CONFLICT"

    return {
        "direction": direction,
        "agreement": state,
        "agreement_score": score,
        "decision_authority": False,
        "execution_authority": False,
    }
