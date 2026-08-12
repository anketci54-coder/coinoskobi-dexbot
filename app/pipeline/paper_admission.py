def paper_admission_decision(strategy, unified_decision, risk_gate):
    """Bind unified intelligence to paper admission conservatively.

    The unified layer has no authority to create a paper buy. It may
    only confirm or downgrade an existing legacy PAPER_BUY. Hard risk
    always dominates.
    """
    legacy = (strategy or {}).get("decision", "REJECT")
    if (risk_gate or {}).get("hard_block"):
        return "REJECT"
    if legacy != "PAPER_BUY":
        return legacy

    unified = (unified_decision or {}).get("decision", "REJECT")
    if unified == "PAPER_BUY_CANDIDATE":
        return "PAPER_BUY"
    if unified == "REQUIRE_MORE_EVIDENCE":
        return "REQUIRE_MORE_EVIDENCE"
    if unified == "WATCH":
        return "WATCH"
    return "REJECT"
