class StrategyEngine:
    """
    Structural prequalification.

    score is evidence coverage only.

    It is NOT:
    - opportunity probability
    - trade permission
    - additive manual points
    - a threshold authority
    """

    FACTS = (
        (
            "token_name",
            lambda token, pair, risk:
            bool(
                token.get("name")
            ),
        ),
        (
            "token_symbol",
            lambda token, pair, risk:
            bool(
                token.get("symbol")
            ),
        ),
        (
            "token_decimals",
            lambda token, pair, risk:
            token.get("decimals")
            is not None,
        ),
        (
            "pair_exists",
            lambda token, pair, risk:
            pair.get("exists")
            is not None,
        ),
        (
            "quote_status",
            lambda token, pair, risk:
            pair.get("quote_ok")
            is not None,
        ),
        (
            "owner_capability",
            lambda token, pair, risk:
            risk.get("owner")
            is not None,
        ),
        (
            "mint_capability",
            lambda token, pair, risk:
            risk.get("mint")
            is not None,
        ),
        (
            "pause_capability",
            lambda token, pair, risk:
            risk.get("pause")
            is not None,
        ),
        (
            "blacklist_capability",
            lambda token, pair, risk:
            risk.get("blacklist")
            is not None,
        ),
        (
            "max_tx_capability",
            lambda token, pair, risk:
            risk.get("max_tx")
            is not None,
        ),
        (
            "max_wallet_capability",
            lambda token, pair, risk:
            risk.get("max_wallet")
            is not None,
        ),
    )

    def evaluate(
        self,
        token,
        pair,
        risk,
    ):
        token = token or {}
        pair = pair or {}
        risk = risk or {}

        coverage = {
            name: bool(
                check(
                    token,
                    pair,
                    risk,
                )
            )
            for name, check
            in self.FACTS
        }

        known = sum(
            1
            for value
            in coverage.values()
            if value
        )

        score = (
            100.0
            * known
            / len(coverage)
        )

        structural_ready = bool(
            token.get("name")
            and token.get(
                "decimals"
            )
            is not None
            and pair.get(
                "exists"
            )
            is True
            and pair.get(
                "quote_ok"
            )
            is True
        )

        if structural_ready:
            decision = "PAPER_BUY"

        elif pair.get(
            "exists"
        ) is False:
            decision = "REJECT"

        else:
            decision = "WATCH"

        warnings = []

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
                warnings.append(label)

        return {
            "success": True,
            "source": "strategy",

            "data": {
                "score": score,

                "score_meaning": (
                    "EVIDENCE_COVERAGE_PERCENT"
                ),

                "score_formula": (
                    "100*known_evidence_fields"
                    "/declared_evidence_fields"
                ),

                "score_authority": False,

                "coverage": coverage,

                "structural_ready": (
                    structural_ready
                ),

                "decision": decision,

                "risk": (
                    "HARD_GATE_OWNS_RISK"
                ),

                "paper_trade": False,

                "reasons": warnings,

                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            },
        }
