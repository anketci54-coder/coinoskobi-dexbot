def evaluate_divergence(
    price_direction,
    spread,
    velocity,
):
    if price_direction not in {"UP", "DOWN"} or spread is None or velocity is None:
        state = "UNKNOWN"
    elif price_direction == "UP":
        if spread < 0:
            state = "PRICE_FLOW_DIVERGENCE"
        elif spread > 0 and velocity > 0:
            state = "STRENGTHENING"
        elif spread > 0 and velocity < 0:
            state = "CONVERGING"
        else:
            state = "NEUTRAL"
    else:
        if spread > 0:
            state = "PRICE_FLOW_DIVERGENCE"
        elif spread < 0 and velocity < 0:
            state = "STRENGTHENING"
        elif spread < 0 and velocity > 0:
            state = "CONVERGING"
        else:
            state = "NEUTRAL"

    return {
        "divergence_state": state,
        "decision_authority": False,
        "execution_authority": False,
    }
