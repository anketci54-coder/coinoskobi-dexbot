def stabilize_trend(
    history,
    current,
    previous="UNKNOWN",
    weakening_confirm=2,
    break_confirm=2,
):
    history = list(history or []) + [current]

    if current == "BREAK":
        need = break_confirm
    elif current == "WEAKENING":
        need = weakening_confirm
    else:
        need = 1

    consecutive = 0
    for state in reversed(history):
        if state != current:
            break
        consecutive += 1

    confirmed = current if consecutive >= need else previous

    return {
        "raw_state": current,
        "confirmed_state": confirmed,
        "consecutive": consecutive,
        "required": need,
        "decision_authority": False,
        "execution_authority": False,
    }
