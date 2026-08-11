def confirm_flow(direction, spread, velocity, participation):
    if direction not in {"BULL", "BEAR"}:
        state = "UNKNOWN"
    elif spread is None or velocity is None:
        state = "UNKNOWN"
    else:
        aligned = (
            direction == "BULL" and spread > 0
        ) or (
            direction == "BEAR" and spread < 0
        )

        strengthening = (
            direction == "BULL" and velocity > 0
        ) or (
            direction == "BEAR" and velocity < 0
        )

        opposite = (
            direction == "BULL" and spread < 0
        ) or (
            direction == "BEAR" and spread > 0
        )

        if opposite:
            state = "CONFLICT"
        elif aligned and strengthening and participation == "DIVERSE":
            state = "CONFIRMED"
        elif aligned:
            state = "PARTIAL_CONFIRMATION"
        else:
            state = "UNCONFIRMED"

    return {
        "confirmation": state,
        "decision_authority": False,
        "execution_authority": False,
    }
