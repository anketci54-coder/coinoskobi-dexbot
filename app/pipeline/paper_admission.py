def paper_admission_decision(
    strategy,
    unified_decision,
    risk_gate,
    *,
    sellability_status,
):
    strategy = strategy or {}
    unified = unified_decision or {}
    gate = risk_gate or {}

    status = str(
        sellability_status
        or "SELLABILITY_SKIPPED"
    )

    if gate.get(
        "hard_block"
    ):
        return "REJECT"

    if (
        status
        == "SELLABILITY_FAIL"
    ):
        return "REJECT"

    if (
        strategy.get(
            "decision"
        )
        != "PAPER_BUY"
    ):
        return (
            "REJECT"
            if (
                strategy.get(
                    "decision"
                )
                == "REJECT"
            )
            else "WATCH"
        )

    if (
        unified.get(
            "decision"
        )
        != "PAPER_BUY_CANDIDATE"
    ):
        return "WATCH"

    if (
        status
        == "SELLABILITY_OK"
    ):
        return "PAPER_BUY"

    return "WATCH"
