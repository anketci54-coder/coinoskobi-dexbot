class RiskGate:
    """
    Strategy skorundan bagimsiz kritik risk kapisi.

    Doktrin:
    - UNKNOWN != RISK
    - Suphe != HARD_BLOCK
    - Yalniz acikca dogrulanmis kritik risk bloklar
    - Gozlem / scoring devam eder
    - Hard block yalniz trade/paper entry'yi durdurur
    """

    def evaluate(self, risk):
        risk = risk or {}

        hard_block_reasons = []
        warning_reasons = []

        honeypot = risk.get("honeypot")
        sellable = risk.get("sellable")

        # --------------------------------------------------------
        # HARD BLOCKS
        # --------------------------------------------------------

        if honeypot is True:
            hard_block_reasons.append(
                "HONEYPOT_CONFIRMED"
            )

        if sellable is False:
            hard_block_reasons.append(
                "SELL_NOT_POSSIBLE"
            )

        # --------------------------------------------------------
        # NON-BLOCKING RISK / TRAP SIGNALS
        #
        # Bunlar tek basina entry bloklamaz.
        # Daha sonra risk score tarafinda kullanilir.
        # --------------------------------------------------------

        if risk.get("mint") is True:
            warning_reasons.append(
                "MINT_CAPABILITY"
            )

        if risk.get("pause") is True:
            warning_reasons.append(
                "PAUSE_CAPABILITY"
            )

        if risk.get("blacklist") is True:
            warning_reasons.append(
                "BLACKLIST_CAPABILITY"
            )

        if risk.get("set_blacklist") is True:
            warning_reasons.append(
                "BLACKLIST_CONTROL"
            )

        if risk.get("max_tx") is True:
            warning_reasons.append(
                "MAX_TX_CONTROL"
            )

        if risk.get("max_wallet") is True:
            warning_reasons.append(
                "MAX_WALLET_CONTROL"
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
            "hard_block": hard_block,
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
        }
