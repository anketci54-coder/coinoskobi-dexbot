def evaluate_runner_health(trend, exhaustion, pressure):
    if "UNKNOWN" in {trend, exhaustion, pressure}:
        state = "UNKNOWN"
    elif trend == "BREAK" and pressure == "HIGH":
        state = "RUNNER_EMERGENCY_EXIT_CONTEXT"
    elif trend == "BREAK":
        state = "RUNNER_EXIT_CANDIDATE"
    elif pressure == "HIGH" or exhaustion == "CONFIRMED":
        state = "RUNNER_TIGHTEN"
    elif trend == "WEAKENING" or pressure == "BUILDING":
        state = "RUNNER_PROTECT"
    else:
        state = "RUNNER_HEALTHY"

    return {
        "runner_health": state,
        "decision_authority": False,
        "execution_authority": False,
    }
