class StrategyEngine:

    def evaluate(self, token, pair, risk):

        score = 0
        reasons = []

        # ERC20

        if token.get("name") not in ("", "?"):
            score += 5
            reasons.append("ERC20 OK")

        if token.get("symbol") not in ("", "?"):
            score += 5
            reasons.append("Symbol OK")

        # Pair

        if pair.get("exists"):
            score += 20
            reasons.append("Pair bulundu")

        if pair.get("quote_ok"):
            score += 15
            reasons.append("Quote alınabiliyor")

        # Bytecode

        code_size = risk.get("code_size", 0)

        if code_size >= 6000:
            score += 20
            reasons.append("Büyük kontrat")

        elif code_size >= 3000:
            score += 15
            reasons.append("Kontrat yeterli")

        elif code_size >= 1500:
            score += 10
            reasons.append("Kontrat küçük")

        else:
            reasons.append("Kontrat çok küçük")

        # Owner

        if not risk.get("owner"):
            score += 10
            reasons.append("Owner yok")

        elif risk.get("renounce_owner"):
            score += 8
            reasons.append("Owner renounce")

        # Mint

        if not risk.get("mint"):
            score += 15
            reasons.append("Mint yok")
        else:
            score -= 30
            reasons.append("Mint var")

        # Pause

        if not risk.get("pause"):
            score += 5
            reasons.append("Pause yok")
        else:
            score -= 10
            reasons.append("Pause var")

        # Blacklist

        if not risk.get("blacklist"):
            score += 5
            reasons.append("Blacklist yok")
        else:
            score -= 15
            reasons.append("Blacklist var")

        # MaxTx

        if not risk.get("max_tx"):
            score += 5
            reasons.append("MaxTx yok")

        # MaxWallet

        if not risk.get("max_wallet"):
            score += 5
            reasons.append("MaxWallet yok")

        # Karar

        if score >= 90:
            decision = "PAPER_BUY"

        elif score >= 70:
            decision = "WATCH"

        else:
            decision = "REJECT"

        return {
            "score": score,
            "decision": decision,
            "reasons": reasons
        }
