def recommend_trailing(current_stop, price, runner_health):
    if current_stop is None or price is None:
        return _out(None, "UNKNOWN")

    ratios = {
        "RUNNER_HEALTHY": 0.90,
        "RUNNER_PROTECT": 0.94,
        "RUNNER_TIGHTEN": 0.97,
        "RUNNER_EXIT_CANDIDATE": 0.99,
        "RUNNER_EMERGENCY_EXIT_CONTEXT": 0.995,
    }

    ratio = ratios.get(runner_health)

    if ratio is None:
        return _out(current_stop, "UNKNOWN")

    proposed = price * ratio
    recommended = max(float(current_stop), proposed)

    return _out(recommended, runner_health)


def _out(stop, state):
    return {
        "recommended_stop": stop,
        "runner_health": state,
        "modify_stop": False,
        "decision_authority": False,
        "execution_authority": False,
    }
