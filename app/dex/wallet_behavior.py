def classify_wallet_behavior(
    buy_count,
    sell_count,
    inbound_value,
    outbound_value,
    interaction_count,
    recent_activity_count,
    previous_activity_count=0,
    freshness="FRESH",
):
    if freshness != "FRESH":
        state = "UNKNOWN"
        tags = []
    else:
        buys = _int(buy_count)
        sells = _int(sell_count)
        inbound = _num(inbound_value)
        outbound = _num(outbound_value)
        interactions = _int(interaction_count)
        recent = _int(recent_activity_count)
        previous = _int(previous_activity_count)

        tags = []

        if buys > sells and inbound > outbound:
            tags.append("ACCUMULATION_EVIDENCE")

        if sells > buys and outbound > inbound:
            tags.append("DISTRIBUTION_EVIDENCE")

        if recent >= max(5, previous * 3):
            tags.append("BURST_ACTIVITY")

        if previous == 0 and recent > 0:
            tags.append("DORMANT_TO_ACTIVE")

        if interactions >= 3:
            tags.append("REPEATED_INTERACTION")

        state = "OBSERVED" if tags else "NEUTRAL"

    return {
        "state": state,
        "behavior_tags": tags,
        "identity_proof": False,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _num(value):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
