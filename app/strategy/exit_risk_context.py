def evaluate_exit_risk(
    sellability,
    liquidity_state,
    mev_risk,
    execution_feasible,
):
    reasons = []

    if sellability is False:
        reasons.append("SELLABILITY_FAIL")

    if liquidity_state in {
        "CRITICAL",
        "COLLAPSE",
        "DRAINING",
    }:
        reasons.append("LIQUIDITY_HARD_RISK")

    if mev_risk in {
        "HIGH",
        "CRITICAL",
    }:
        reasons.append("MEV_HIGH_RISK")

    if execution_feasible is False:
        reasons.append("EXECUTION_NOT_FEASIBLE")

    hard = bool(reasons)

    return {
        "hard_risk": hard,
        "reasons": reasons,
        "trend_override": hard,
        "decision_authority": False,
        "execution_authority": False,
    }
