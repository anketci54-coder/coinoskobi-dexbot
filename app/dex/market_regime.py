def classify_market_regime(direction, confirmation, divergence, quality):
    if "UNKNOWN" in {direction, confirmation, divergence, quality}:
        state = "UNKNOWN"
    elif confirmation == "CONFLICT" or divergence == "PRICE_FLOW_DIVERGENCE":
        state = "CONFLICT"
    elif quality == "SINGLE_ACTOR_SPIKE":
        state = "CHOP"
    elif (
        confirmation == "CONFIRMED"
        and divergence == "STRENGTHENING"
        and quality == "MULTI_ACTOR"
    ):
        if direction == "BULL":
            state = "TRENDING_BULL"
        elif direction == "BEAR":
            state = "TRENDING_BEAR"
        else:
            state = "UNKNOWN"
    elif confirmation in {"PARTIAL_CONFIRMATION", "UNCONFIRMED"} \
         or divergence == "CONVERGING":
        state = "TRANSITION"
    else:
        state = "CHOP"

    return {
        "market_regime": state,
        "decision_authority": False,
        "execution_authority": False,
    }
