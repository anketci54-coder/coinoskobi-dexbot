def bind_runner_exit(runner_state, guidance):
    runner = runner_state or {}
    guide = guidance or {}

    action = guide.get("guidance", "UNKNOWN")
    active = bool(runner.get("runner_active"))

    if not active:
        recommendation = "NO_RUNNER"
    elif action == "CONTINUE":
        recommendation = "KEEP_RUNNING"
    elif action == "PROTECT":
        recommendation = "TIGHTEN_PROTECTION"
    elif action == "EXIT_CANDIDATE":
        recommendation = "PREPARE_EXIT"
    else:
        recommendation = "HOLD_CURRENT_PROTECTION"

    return {
        "runner_active": active,
        "guidance": action,
        "recommendation": recommendation,
        "modify_stop": False,
        "execute_exit": False,
        "decision_authority": False,
        "execution_authority": False,
    }
