from app.config.risk import (
    UNIFIED_DECISION_MIN_CONFIDENCE,
    UNIFIED_DECISION_PAPER_SCORE,
    UNIFIED_DECISION_WATCH_SCORE,
)


DECISION_REJECT = "REJECT"
DECISION_WATCH = "WATCH"
DECISION_MORE_EVIDENCE = (
    "REQUIRE_MORE_EVIDENCE"
)
DECISION_PAPER_CANDIDATE = (
    "PAPER_BUY_CANDIDATE"
)


class UnifiedDecisionEngine:
    """
    Unified decision contract v1.

    This layer interprets Unified Score.

    It does NOT:
    - execute trades
    - open positions
    - sign transactions
    - override RiskGate
    - calculate Entry / SL / TP
    - calculate final execution economics

    Confidence is evidence coverage,
    not win probability.
    """

    def evaluate(self, unified_score):
        unified_score = (
            unified_score or {}
        )

        try:
            score = float(
                unified_score.get(
                    "score",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            score = 0.0

        try:
            confidence = float(
                unified_score.get(
                    "confidence",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = 0.0

        hard_block = bool(
            unified_score.get(
                "hard_block"
            )
        )

        reasons = []

        # --------------------------------------------------------
        # Constitutional boundary
        # --------------------------------------------------------

        if hard_block:
            decision = DECISION_REJECT

            reasons.append(
                "HARD_BLOCK"
            )

        # --------------------------------------------------------
        # Strong score but incomplete evidence
        # --------------------------------------------------------

        elif (
            score
            >= UNIFIED_DECISION_PAPER_SCORE
        ):
            if (
                confidence
                >= UNIFIED_DECISION_MIN_CONFIDENCE
            ):
                decision = (
                    DECISION_PAPER_CANDIDATE
                )

                reasons.append(
                    "SCORE_AND_EVIDENCE_READY"
                )

            else:
                decision = (
                    DECISION_MORE_EVIDENCE
                )

                reasons.append(
                    "HIGH_SCORE_LOW_CONFIDENCE"
                )

        # --------------------------------------------------------
        # Watch zone
        # --------------------------------------------------------

        elif (
            score
            >= UNIFIED_DECISION_WATCH_SCORE
        ):
            decision = DECISION_WATCH

            reasons.append(
                "SCORE_IN_WATCH_ZONE"
            )

        # --------------------------------------------------------
        # Reject zone
        # --------------------------------------------------------

        else:
            decision = DECISION_REJECT

            reasons.append(
                "SCORE_BELOW_WATCH"
            )

        return {
            "model": (
                "unified_decision_v1"
            ),
            "decision": decision,
            "score": score,
            "confidence": confidence,
            "hard_block": hard_block,
            "reasons": reasons,

            "thresholds": {
                "paper_score": (
                    UNIFIED_DECISION_PAPER_SCORE
                ),
                "watch_score": (
                    UNIFIED_DECISION_WATCH_SCORE
                ),
                "min_confidence": (
                    UNIFIED_DECISION_MIN_CONFIDENCE
                ),
            },

            # ----------------------------------------------------
            # Authority boundary
            # ----------------------------------------------------

            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
