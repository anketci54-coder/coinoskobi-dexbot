def analyze_whale_flow(
    total_value,
    largest_wallet_value,
    whale_inflow,
    whale_outflow,
    unique_whales,
    cex_bridge=False,
    dust_ratio=0.0,
    freshness="FRESH",
):
    if freshness != "FRESH":
        return _out("UNKNOWN", [], None)

    total = _num(total_value)
    largest = _num(largest_wallet_value)
    inflow = _num(whale_inflow)
    outflow = _num(whale_outflow)
    whales = _int(unique_whales)
    dust = _ratio(dust_ratio)

    if total <= 0:
        return _out("UNKNOWN", [], None)

    share = min(1.0, largest / total)
    tags = []

    if dust >= 0.50:
        tags.append("DUST_NOISE")

    if share >= 0.70:
        tags.append("SINGLE_WHALE_DOMINANCE")
    elif whales >= 3:
        tags.append("MULTI_WHALE_ACTIVITY")

    if inflow > outflow:
        tags.append("WHALE_NET_INFLOW")
    elif outflow > inflow:
        tags.append("WHALE_NET_OUTFLOW")

    if cex_bridge:
        tags.append("CEX_BRIDGE_EVIDENCE")

    if "DUST_NOISE" in tags:
        state = "NOISY"
    elif "SINGLE_WHALE_DOMINANCE" in tags:
        state = "CONCENTRATED"
    elif "MULTI_WHALE_ACTIVITY" in tags:
        state = "DISTRIBUTED"
    else:
        state = "LIMITED"

    return _out(state, tags, share)


def _out(state, tags, share):
    return {
        "state": state,
        "tags": tags,
        "largest_wallet_share": share,
        "trade_signal": False,
        "decision_authority": False,
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


def _ratio(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0
