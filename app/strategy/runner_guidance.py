def runner_guidance(confirmed_trend):
    mapping = {
        "STRONG": "CONTINUE",
        "HEALTHY": "CONTINUE",
        "WEAKENING": "PROTECT",
        "BREAK": "EXIT_CANDIDATE",
        "UNKNOWN": "UNKNOWN",
    }

    guidance = mapping.get(
        confirmed_trend,
        "UNKNOWN",
    )

    return {
        "trend": confirmed_trend,
        "guidance": guidance,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
