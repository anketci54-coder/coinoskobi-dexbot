class UnifiedDecisionEngine:
    """
    Canonical opportunity-state decision.

    This layer no longer converts evidence completeness into entry intent.
    Only a HOT opportunity may become a PAPER_BUY_CANDIDATE. Missing evidence
    remains observable as WATCH. Confirmed hard risk remains REJECT.
    """

    def evaluate(self, unified_score):
        data = unified_score or {}
        reasons = []

        opportunity_state = str(
            data.get("opportunity_state") or "WATCH"
        ).upper()

        opportunity_reason = str(
            data.get("opportunity_reason") or "OPPORTUNITY_NOT_READY"
        )

        if data.get("hard_block"):
            decision = "REJECT"
            reasons.append("HARD_BLOCK")

        elif data.get("strategy_decision") == "REJECT":
            decision = "REJECT"
            reasons.append("STRUCTURAL_REJECT")

        elif data.get("sellability") == "UNSELLABLE":
            decision = "REJECT"
            reasons.append("SELLABILITY_FAIL")

        elif opportunity_state == "REJECT":
            decision = "REJECT"
            reasons.append(opportunity_reason)

        elif opportunity_state != "HOT":
            decision = "WATCH"
            reasons.append(opportunity_reason)

        elif data.get("sellability") == "SELLABLE":
            decision = "PAPER_BUY_CANDIDATE"
            reasons.extend([
                "ACTIVE_OPPORTUNITY_HOT",
                "VERIFIED_SELLABILITY",
            ])

        elif data.get("local_evidence_complete"):
            # External provider may be unavailable. Local onchain exit evidence
            # can keep the candidate alive, but final mathematical planning and
            # sellability policy still decide whether a PAPER order is allowed.
            decision = "PAPER_BUY_CANDIDATE"
            reasons.extend([
                "ACTIVE_OPPORTUNITY_HOT",
                "LOCAL_EXIT_EVIDENCE_READY",
            ])

        else:
            decision = "WATCH"
            reasons.append("EXIT_EVIDENCE_NOT_READY")

        return {
            "model": "unified_decision_v1",
            "decision": decision,
            "reasons": reasons,
            "opportunity_state": opportunity_state,
            "opportunity_reason": opportunity_reason,
            "score_threshold_used": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
