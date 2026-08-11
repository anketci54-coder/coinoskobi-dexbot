def build_runner_exit_contract(
    trend_health,
    exhaustion,
    runner_health,
    trailing,
    exit_pressure,
    risk_context,
    freshness,
    reasons=None,
):
    reasons = list(reasons or [])

    if risk_context and risk_context.get("reasons"):
        reasons.extend(risk_context["reasons"])

    return {
        "trend_health": trend_health,
        "exhaustion_state": exhaustion,
        "runner_health": runner_health,
        "trailing_recommendation": trailing,
        "exit_pressure": exit_pressure,
        "hard_risk": bool(
            risk_context and risk_context.get("hard_risk")
        ),
        "freshness": freshness,
        "reasons": reasons,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
