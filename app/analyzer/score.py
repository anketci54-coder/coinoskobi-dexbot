def calculate_score(info, risk, pair):

    score = 0
    reasons = []

    if info.get("name") != "?":
        score += 10
        reasons.append("ERC20 OK")

    if info.get("symbol") != "?":
        score += 5
        reasons.append("Symbol OK")

    if pair.get("exists", False):
        score += 20
        reasons.append("Pair bulundu")

    if pair.get("quote_ok", False):
        score += 20
        reasons.append("Quote OK")

    if not risk.get("mint", False):
        score += 15
        reasons.append("Mint yok")

    if not risk.get("pause", False):
        score += 5
        reasons.append("Pause yok")

    if not risk.get("max_tx", False):
        score += 5
        reasons.append("MaxTx yok")

    if not risk.get("max_wallet", False):
        score += 5
        reasons.append("MaxWallet yok")

    if score >= 90:
        decision = "BUY_READY"
    elif score >= 70:
        decision = "WATCH"
    elif score >= 50:
        decision = "WAIT"
    else:
        decision = "REJECT"

    return {
        "score": score,
        "decision": decision,
        "reasons": reasons
    }
