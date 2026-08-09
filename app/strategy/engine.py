class StrategyEngine:

    def evaluate(self, token, pair, risk):

        score = 0
        reasons = []

        # ERC20

        token_name = token.get("name")

        if token_name not in (None, "", "?"):
            score += 5
            reasons.append("ERC20 OK")

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

        owner = risk.get("owner")

        if owner is False:
            score += 10
            reasons.append("Owner yok")

        elif owner is True and risk.get("renounce_owner") is True:
            score += 8
            reasons.append("Owner renounce")

        # Mint

        mint = risk.get("mint")

        if mint is False:
            score += 15
            reasons.append("Mint yok")
        elif mint is True:
            score -= 30
            reasons.append("Mint var")

        # Pause

        pause = risk.get("pause")

        if pause is False:
            score += 5
            reasons.append("Pause yok")
        elif pause is True:
            score -= 10
            reasons.append("Pause var")

        # Blacklist

        blacklist = risk.get("blacklist")

        if blacklist is False:
            score += 5
            reasons.append("Blacklist yok")
        elif blacklist is True:
            score -= 15
            reasons.append("Blacklist var")

        # MaxTx

        if risk.get("max_tx") is False:
            score += 5
            reasons.append("MaxTx yok")

        # MaxWallet

        if risk.get("max_wallet") is False:
            score += 5
            reasons.append("MaxWallet yok")

        # Karar

        if score >= 90:
            decision = "PAPER_BUY"

        elif score >= 70:
            decision = "WATCH"

        else:
            decision = "REJECT"

        # Risk level

        if score >= 90:
            risk_level = "LOW"
        elif score >= 70:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        # Paper trade flag

        paper_trade = decision == "PAPER_BUY"

        return {
            "success": True,
            "source": "strategy",
            "data": {
                "decision": decision,
                "score": score,
                "reasons": reasons,
                "risk": risk_level,
                "paper_trade": paper_trade,
            },
        }
