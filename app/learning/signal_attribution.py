ALLOWED_STATES = {
    "SUPPORTS_OUTCOME",
    "OPPOSES_OUTCOME",
    "NEUTRAL",
    "UNKNOWN",
}


def attribute_signals(
    outcome_class,
    signal_states,
    hard_safety_signals=None,
    freshness="FRESH",
    evidence_complete=True,
):
    if freshness != "FRESH" or not evidence_complete:
        return _out(
            state="UNKNOWN",
            normalized={},
            supporting=[],
            opposing=[],
            neutral=[],
            unknown=[],
            hard_safety=[],
        )

    if not outcome_class or outcome_class == "UNKNOWN":
        return _out(
            state="UNKNOWN",
            normalized={},
            supporting=[],
            opposing=[],
            neutral=[],
            unknown=[],
            hard_safety=[],
        )

    normalized = {}

    for family, raw_state in dict(signal_states or {}).items():
        state = str(raw_state or "UNKNOWN").upper()

        if state not in ALLOWED_STATES:
            state = "UNKNOWN"

        normalized[str(family)] = state

    supporting = sorted(
        family
        for family, state in normalized.items()
        if state == "SUPPORTS_OUTCOME"
    )

    opposing = sorted(
        family
        for family, state in normalized.items()
        if state == "OPPOSES_OUTCOME"
    )

    neutral = sorted(
        family
        for family, state in normalized.items()
        if state == "NEUTRAL"
    )

    unknown = sorted(
        family
        for family, state in normalized.items()
        if state == "UNKNOWN"
    )

    hard_safety = sorted(
        str(x)
        for x in (hard_safety_signals or [])
        if x
    )

    if supporting and opposing:
        state = "CONFLICTING_ATTRIBUTION"
    elif supporting:
        state = "SUPPORTED_ATTRIBUTION"
    elif opposing:
        state = "OPPOSED_ATTRIBUTION"
    elif normalized:
        state = "UNRESOLVED_ATTRIBUTION"
    else:
        state = "UNKNOWN"

    return _out(
        state=state,
        normalized=normalized,
        supporting=supporting,
        opposing=opposing,
        neutral=neutral,
        unknown=unknown,
        hard_safety=hard_safety,
    )


def _out(
    state,
    normalized,
    supporting,
    opposing,
    neutral,
    unknown,
    hard_safety,
):
    known_count = (
        len(supporting)
        + len(opposing)
        + len(neutral)
    )

    return {
        "state": state,
        "signal_states": normalized,
        "supporting_signals": supporting,
        "opposing_signals": opposing,
        "neutral_signals": neutral,
        "unknown_signals": unknown,
        "hard_safety_signals": hard_safety,
        "known_signal_count": known_count,
        "support_count": len(supporting),
        "opposition_count": len(opposing),
        "correlation_is_causation": False,
        "single_signal_owns_outcome": False,
        "hard_safety_separate_from_soft_attribution": True,
        "hindsight_rewrite_allowed": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
