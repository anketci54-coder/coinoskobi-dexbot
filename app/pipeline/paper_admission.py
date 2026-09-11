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

    # Paper admission is intentionally less strict than the unified HOT/live
    # entry lane. A strategy PAPER_BUY with no hard risk and confirmed
    # sellability is safe to record as a paper position even while unified
    # opportunity remains WATCH (for example, momentum has not turned
    # positive yet). Unified REJECT is still a paper-entry veto.
    if (
        unified.get(
            "decision"
        )
        == "REJECT"
    ):
        return "WATCH"

    if (
        status
        == "SELLABILITY_OK"
    ):
        return "PAPER_BUY"

    return "WATCH"
