def stabilize_confirmation(
    history,
    current,
    previous="UNKNOWN",
    confirm_ticks=2,
    conflict_ticks=2,
):
    history = list(history or []) + [current]

    if current in {"CONFIRMED", "CONFLICT"}:
        need = confirm_ticks if current == "CONFIRMED" else conflict_ticks
    else:
        need = 1

    count = 0
    for state in reversed(history):
        if state != current:
            break
        count += 1

    stable = current if count >= need else previous

    return {
        "raw_state": current,
        "stable_state": stable,
        "consecutive": count,
        "required": need,
        "decision_authority": False,
        "execution_authority": False,
    }
