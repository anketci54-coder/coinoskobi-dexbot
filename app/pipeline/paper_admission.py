def paper_admission_decision(
    strategy,
    unified_decision,
    risk_gate,
    sellability_status=None,
):
    """Final conservative PAPER admission boundary.

    PAPER_BUY requires:
    - legacy PAPER_BUY
    - unified PAPER_BUY_CANDIDATE
    - no hard block
    - explicitly verified sellability

    Missing / skipped sellability evidence can remain observable
    as WATCH but cannot create a new paper position.
    """

    legacy = (strategy or {}).get(
        "decision",
        "REJECT",
    )

    if (risk_gate or {}).get("hard_block"):
        return "REJECT"

    if legacy != "PAPER_BUY":
        return legacy

    unified = (unified_decision or {}).get(
        "decision",
        "REJECT",
    )

    if unified == "REQUIRE_MORE_EVIDENCE":
        return "REQUIRE_MORE_EVIDENCE"

    if unified == "WATCH":
        return "WATCH"

    if unified != "PAPER_BUY_CANDIDATE":
        return "REJECT"

    status = str(
        sellability_status or ""
    ).strip().upper()

    blocked = {
        "SELLABILITY_FAIL",
        "SELLABILITY_BLOCK",
        "UNSELLABLE",
    }

    verified = {
        "SELLABILITY_OK",
        "SELLABLE",
        "PASS",
    }

    if status in blocked:
        return "REJECT"

    if status not in verified:
        return "WATCH"

    return "PAPER_BUY"
