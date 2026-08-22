class UnifiedScoreEngine:
    """
    Evidence coverage readmodel.

    This score never grants entry authority.
    """

    def evaluate(
        self,
        *,
        strategy,
        risk_gate,
        trap_risk,
        mev_risk,
    ):
        strategy = strategy or {}
        risk_gate = risk_gate or {}
        trap_risk = trap_risk or {}
        mev_risk = mev_risk or {}

        trap_evidence = (
            trap_risk.get(
                "evidence"
            )
            or {}
        )

        sellability = (
            risk_gate.get(
                "sellability",
                "UNKNOWN",
            )
        )

        honeypot = (
            risk_gate.get(
                "honeypot",
                "UNKNOWN",
            )
        )

        mev_status = (
            mev_risk.get(
                "status",
                "UNKNOWN",
            )
        )

        coverage = {
            "strategy": (
                strategy.get(
                    "decision"
                )
                is not None
            ),

            "sellability": (
                sellability
                in {
                    "SELLABLE",
                    "UNSELLABLE",
                }
            ),

            "honeypot": (
                honeypot
                in {
                    "YES",
                    "NO",
                }
            ),

            "tax": any(
                trap_evidence.get(
                    key
                )
                is not None
                for key in (
                    "buy_tax",
                    "sell_tax",
                    "round_trip_tax",
                )
            ),

            "mev": (
                mev_status
                not in {
                    None,
                    "UNKNOWN",
                }
            ),

            "local_market": bool(
                risk_gate.get(
                    "local_evidence_complete"
                )
            ),
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

        return {
            "model": "unified_score_v1",

            "score": score,

            "confidence": score,

            "opportunity_score": None,

            "score_meaning": (
                "EVIDENCE_COVERAGE_PERCENT"
            ),

            "score_formula": (
                "100*known_evidence_dimensions"
                "/declared_evidence_dimensions"
            ),

            "score_authority": False,

            "coverage": coverage,

            "strategy_decision": (
                strategy.get(
                    "decision"
                )
            ),

            "structural_ready": bool(
                strategy.get(
                    "structural_ready"
                )
            ),

            "sellability": sellability,

            "honeypot": honeypot,

            "local_evidence_complete": (
                bool(
                    risk_gate.get(
                        "local_evidence_complete"
                    )
                )
            ),

            "hard_block": bool(
                risk_gate.get(
                    "hard_block"
                )
            ),

            # Historical interface keys remain,
            # but manual penalty scoring is gone.
            "tax_penalty": None,
            "mev_penalty": None,
            "total_penalty": None,

            "decision_authority": False,
            "paper_authority": False,
            "trade_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
