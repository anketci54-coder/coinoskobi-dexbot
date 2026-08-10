from app.config.strategy import (
    CONTRACT_SIZE_LARGE,
    CONTRACT_SIZE_OK,
    CONTRACT_SIZE_SMALL,
    PAPER_BUY_SCORE,
    PENALTY_BLACKLIST_ENABLED,
    PENALTY_MINT_ENABLED,
    PENALTY_PAUSE_ENABLED,
    SCORE_BLACKLIST_NONE,
    SCORE_CONTRACT_LARGE,
    SCORE_CONTRACT_OK,
    SCORE_CONTRACT_SMALL,
    SCORE_ERC20_OK,
    SCORE_MAX_TX_NONE,
    SCORE_MAX_WALLET_NONE,
    SCORE_MINT_NONE,
    SCORE_OWNER_NONE,
    SCORE_OWNER_RENOUNCED,
    SCORE_PAIR_EXISTS,
    SCORE_PAUSE_NONE,
    SCORE_QUOTE_OK,
    WATCH_SCORE,
)


class StrategyEngine:

    def evaluate(self, token, pair, risk):

        score = 0
        reasons = []

        # ERC20

        token_name = token.get("name")

        if token_name not in (
            None,
            "",
            "?",
        ):
            score += SCORE_ERC20_OK
            reasons.append("ERC20 OK")

        # Pair

        if pair.get("exists"):
            score += SCORE_PAIR_EXISTS
            reasons.append("Pair bulundu")

        if pair.get("quote_ok"):
            score += SCORE_QUOTE_OK
            reasons.append("Quote alınabiliyor")

        # Bytecode

        code_size = risk.get(
            "code_size",
            0,
        )

        if code_size >= CONTRACT_SIZE_LARGE:
            score += SCORE_CONTRACT_LARGE
            reasons.append("Büyük kontrat")

        elif code_size >= CONTRACT_SIZE_OK:
            score += SCORE_CONTRACT_OK
            reasons.append("Kontrat yeterli")

        elif code_size >= CONTRACT_SIZE_SMALL:
            score += SCORE_CONTRACT_SMALL
            reasons.append("Kontrat küçük")

        else:
            reasons.append("Kontrat çok küçük")

        # Owner

        owner = risk.get("owner")

        if owner is False:
            score += SCORE_OWNER_NONE
            reasons.append("Owner yok")

        elif (
            owner is True
            and risk.get(
                "renounce_owner"
            ) is True
        ):
            score += SCORE_OWNER_RENOUNCED
            reasons.append("Owner renounce")

        # Mint

        mint = risk.get("mint")

        if mint is False:
            score += SCORE_MINT_NONE
            reasons.append("Mint yok")

        elif mint is True:
            score -= PENALTY_MINT_ENABLED
            reasons.append("Mint var")

        # Pause

        pause = risk.get("pause")

        if pause is False:
            score += SCORE_PAUSE_NONE
            reasons.append("Pause yok")

        elif pause is True:
            score -= PENALTY_PAUSE_ENABLED
            reasons.append("Pause var")

        # Blacklist

        blacklist = risk.get(
            "blacklist"
        )

        if blacklist is False:
            score += SCORE_BLACKLIST_NONE
            reasons.append("Blacklist yok")

        elif blacklist is True:
            score -= PENALTY_BLACKLIST_ENABLED
            reasons.append("Blacklist var")

        # MaxTx

        if risk.get("max_tx") is False:
            score += SCORE_MAX_TX_NONE
            reasons.append("MaxTx yok")

        # MaxWallet

        if risk.get("max_wallet") is False:
            score += SCORE_MAX_WALLET_NONE
            reasons.append("MaxWallet yok")

        # Decision

        if score >= PAPER_BUY_SCORE:
            decision = "PAPER_BUY"

        elif score >= WATCH_SCORE:
            decision = "WATCH"

        else:
            decision = "REJECT"

        # Risk level

        if score >= PAPER_BUY_SCORE:
            risk_level = "LOW"

        elif score >= WATCH_SCORE:
            risk_level = "MEDIUM"

        else:
            risk_level = "HIGH"

        paper_trade = (
            decision == "PAPER_BUY"
        )

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
