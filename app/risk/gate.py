class RiskGate:
    """
    Confirmed hard facts block.

    Missing evidence remains UNKNOWN.
    Mathematical opportunity cannot override
    a hard safety fact.
    """

    def evaluate(self, risk):
        risk = risk or {}

        hard_block_reasons = []
        warning_reasons = []

        honeypot = risk.get(
            "honeypot"
        )

        sellable = risk.get(
            "sellable"
        )

        if honeypot is True:
            hard_block_reasons.append(
                "HONEYPOT_CONFIRMED"
            )

        if sellable is False:
            hard_block_reasons.append(
                "SELL_NOT_POSSIBLE"
            )

        for key, label in (
            (
                "mint",
                "MINT_CAPABILITY",
            ),
            (
                "pause",
                "PAUSE_CAPABILITY",
            ),
            (
                "blacklist",
                "BLACKLIST_CAPABILITY",
            ),
            (
                "set_blacklist",
                "BLACKLIST_CONTROL",
            ),
            (
                "max_tx",
                "MAX_TX_CONTROL",
            ),
            (
                "max_wallet",
                "MAX_WALLET_CONTROL",
            ),
        ):
            if risk.get(key) is True:
                warning_reasons.append(
                    label
                )

        local = risk.get(
            "local_evidence"
        )

        local_complete = bool(
            isinstance(
                local,
                dict,
            )
            and local.get(
                "completed"
            )
            is True
        )

        hard_block = bool(
            hard_block_reasons
        )

        if hard_block:
            status = "BLOCK"

        elif warning_reasons:
            status = "CAUTION"

        else:
            status = "PASS"

        return {
            "hard_block": (
                hard_block
            ),

            "status": status,

            "hard_block_reasons": (
                hard_block_reasons
            ),

            "warning_reasons": (
                warning_reasons
            ),

            "sellability": (
                "SELLABLE"
                if sellable is True
                else (
                    "UNSELLABLE"
                    if sellable is False
                    else "UNKNOWN"
                )
            ),

            "honeypot": (
                "YES"
                if honeypot is True
                else (
                    "NO"
                    if honeypot is False
                    else "UNKNOWN"
                )
            ),

            "local_evidence": local,

            "local_evidence_complete": (
                local_complete
            ),

            "decision_authority": False,
            "paper_authority": False,
            "trade_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
