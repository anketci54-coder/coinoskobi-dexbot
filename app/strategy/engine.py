class StrategyEngine:

    def evaluate(self, token_info, pair_info, risk_info):

        score = 0
        reasons = []

        if token_info["name"] != "?":
            score += 10
            reasons.append("ERC20 OK")

        if token_info["symbol"] != "?":
            score += 5
            reasons.append("Symbol OK")

        if pair_info["exists"]:
            score += 20
            reasons.append("Pair bulundu")

        if pair_info["quote_ok"]:
            score += 20
            reasons.append("Quote alınabiliyor")

        if not risk_info["mint"]:
            score += 15
            reasons.append("Mint yok")

        if not risk_info["pause"]:
            score += 5
            reasons.append("Pause yok")

        if not risk_info["max_tx"]:
            score += 5
            reasons.append("MaxTx yok")

        if not risk_info["max_wallet"]:
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
