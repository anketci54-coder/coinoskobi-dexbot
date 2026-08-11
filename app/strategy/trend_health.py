def classify_trend_health(ctx):
    ctx = ctx or {}

    if not ctx.get("data_ready"):
        state = "UNKNOWN"
    elif ctx.get("state") == "EXIT_PRESSURE":
        state = "BREAK"
    elif ctx.get("state") == "WEAKENING":
        state = "WEAKENING"
    elif ctx.get("state") == "HOLDING":
        m = ctx.get("flow_momentum")
        a = ctx.get("flow_acceleration")
        state = "STRONG" if m is not None and a is not None and m > 0 and a > 0 else "HEALTHY"
    elif ctx.get("state") == "NEUTRAL":
        state = "HEALTHY"
    else:
        state = "UNKNOWN"

    return {
        "trend_health": state,
        "source_state": ctx.get("state"),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
