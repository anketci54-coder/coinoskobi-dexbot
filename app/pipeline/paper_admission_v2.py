def paper_admission_decision_v2(strategy, unified_decision, risk_gate, *, sellability_status):
    strategy = strategy or {}
    unified = unified_decision or {}
    gate = risk_gate or {}
    status = str(sellability_status or "SELLABILITY_SKIPPED")
    if gate.get("hard_block") or status == "SELLABILITY_FAIL":
        return "REJECT"
    if strategy.get("decision") != "PAPER_BUY":
        return "REJECT" if strategy.get("decision") == "REJECT" else "WATCH"
    if unified.get("decision") == "REJECT":
        return "WATCH"
    if status == "SELLABILITY_OK":
        return "PAPER_BUY"
    return "WATCH"
