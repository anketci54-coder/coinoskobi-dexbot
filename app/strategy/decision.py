class UnifiedDecisionEngine:
    """
    Evidence-state decision.

    No numeric score threshold is used.
    """

    def evaluate(
        self,
        unified_score,
    ):
        data = unified_score or {}

        reasons = []

        if data.get(
            "hard_block"
        ):
            decision = "REJECT"

            reasons.append(
                "HARD_BLOCK"
            )

        elif (
            data.get(
                "strategy_decision"
            )
            == "REJECT"
        ):
            decision = "REJECT"

            reasons.append(
                "STRUCTURAL_REJECT"
            )

        elif (
            data.get(
                "strategy_decision"
            )
            != "PAPER_BUY"
        ):
            decision = "WATCH"

            reasons.append(
                "STRUCTURAL_EVIDENCE_NOT_READY"
            )

        elif (
            data.get(
                "sellability"
            )
            == "UNSELLABLE"
        ):
            decision = "REJECT"

            reasons.append(
                "SELLABILITY_FAIL"
            )

        elif (
            data.get(
                "sellability"
            )
            == "SELLABLE"
        ):
            decision = (
                "PAPER_BUY_CANDIDATE"
            )

            reasons.append(
                "VERIFIED_SELLABILITY"
            )

        elif data.get(
            "local_evidence_complete"
        ):
            decision = (
                "PAPER_BUY_CANDIDATE"
            )

            reasons.append(
                "LOCAL_MATHEMATICAL_EVIDENCE_READY"
            )

        else:
            decision = (
                "REQUIRE_MORE_EVIDENCE"
            )

            reasons.append(
                "MISSING_ENTRY_EVIDENCE"
            )

        return {
            "model": "unified_decision_v1",

            "decision": decision,

            "reasons": reasons,

            "score_threshold_used": False,

            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
