from app.config.risk import (
    UNIFIED_CONFIDENCE_MEV_WEIGHT,
    UNIFIED_CONFIDENCE_SELLABILITY_WEIGHT,
    UNIFIED_CONFIDENCE_STRATEGY_WEIGHT,
    UNIFIED_CONFIDENCE_TAX_WEIGHT,
    UNIFIED_MEV_PENALTY_CRITICAL,
    UNIFIED_MEV_PENALTY_HIGH,
    UNIFIED_MEV_PENALTY_LOW,
    UNIFIED_MEV_PENALTY_MEDIUM,
    UNIFIED_STRATEGY_MAX_RAW_SCORE,
    UNIFIED_TAX_PENALTY_CRITICAL,
    UNIFIED_TAX_PENALTY_HIGH,
    UNIFIED_TAX_PENALTY_LOW,
    UNIFIED_TAX_PENALTY_MEDIUM,
)


def _clamp(
    value,
    minimum=0.0,
    maximum=100.0,
):
    return max(
        minimum,
        min(maximum, float(value)),
    )


class UnifiedScoreEngine:
    """
    Unified Score v1.

    Properties:
    - deterministic
    - explainable
    - pure local
    - no RPC / HTTP
    - no trade authority
    - UNKNOWN does not become a penalty
    - hard-block remains separate

    Important:
    Legacy strategy already scores several
    contract-control risks.

    Therefore trap contract signals such as
    MINT_CAPABILITY / PAUSE_CAPABILITY /
    BLACKLIST_CAPABILITY are NOT deducted here.

    Only dimensions not already represented are
    added in v1:
    - tax
    - MEV / sandwich exposure
    """

    TAX_PREFIXES = (
        "BUY_TAX_",
        "SELL_TAX_",
        "TRANSFER_TAX_",
        "ROUND_TRIP_TAX_",
    )

    TAX_PENALTY = {
        "LOW": UNIFIED_TAX_PENALTY_LOW,
        "MEDIUM": UNIFIED_TAX_PENALTY_MEDIUM,
        "HIGH": UNIFIED_TAX_PENALTY_HIGH,
        "CRITICAL": (
            UNIFIED_TAX_PENALTY_CRITICAL
        ),
    }

    MEV_PENALTY = {
        "LOW": UNIFIED_MEV_PENALTY_LOW,
        "MEDIUM": UNIFIED_MEV_PENALTY_MEDIUM,
        "HIGH": UNIFIED_MEV_PENALTY_HIGH,
        "CRITICAL": (
            UNIFIED_MEV_PENALTY_CRITICAL
        ),
    }

    @staticmethod
    def _strategy_score(strategy):
        strategy = strategy or {}

        try:
            raw = float(
                strategy.get("score", 0)
            )
        except (
            TypeError,
            ValueError,
        ):
            raw = 0.0

        normalized = (
            raw
            / UNIFIED_STRATEGY_MAX_RAW_SCORE
            * 100.0
        )

        return (
            raw,
            _clamp(normalized),
        )

    def _tax_penalty(
        self,
        trap_risk,
    ):
        trap_risk = trap_risk or {}

        penalties = []
        evidence = []

        # Avoid double counting multiple tax signals
        # by taking only the strongest tax severity.
        strongest_rank = 0
        strongest_severity = None

        rank = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
        }

        for signal in trap_risk.get(
            "signals",
            [],
        ):
            code = str(
                signal.get("code", "")
            )

            if not code.startswith(
                self.TAX_PREFIXES
            ):
                continue

            severity = signal.get(
                "severity"
            )

            evidence.append(code)

            candidate_rank = rank.get(
                severity,
                0,
            )

            if candidate_rank > strongest_rank:
                strongest_rank = (
                    candidate_rank
                )
                strongest_severity = (
                    severity
                )

        if strongest_severity:
            penalty = self.TAX_PENALTY.get(
                strongest_severity,
                0.0,
            )

            penalties.append({
                "dimension": "tax",
                "severity": (
                    strongest_severity
                ),
                "penalty": penalty,
            })

            return (
                penalty,
                penalties,
                evidence,
            )

        return (
            0.0,
            penalties,
            evidence,
        )

    def _mev_penalty(
        self,
        mev_risk,
    ):
        mev_risk = mev_risk or {}

        severity = mev_risk.get(
            "severity"
        )

        if severity not in (
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        ):
            return (
                0.0,
                [],
            )

        penalty = self.MEV_PENALTY.get(
            severity,
            0.0,
        )

        return (
            penalty,
            [{
                "dimension": "mev",
                "severity": severity,
                "penalty": penalty,
            }],
        )

    @staticmethod
    def _confidence(
        risk_gate,
        trap_risk,
        mev_risk,
    ):
        risk_gate = risk_gate or {}
        trap_risk = trap_risk or {}
        mev_risk = mev_risk or {}

        confidence = (
            UNIFIED_CONFIDENCE_STRATEGY_WEIGHT
        )

        coverage = {
            "strategy": True,
            "sellability": False,
            "tax": False,
            "mev": False,
        }

        sellability = risk_gate.get(
            "sellability",
            "UNKNOWN",
        )

        honeypot = risk_gate.get(
            "honeypot",
            "UNKNOWN",
        )

        if (
            sellability != "UNKNOWN"
            or honeypot != "UNKNOWN"
        ):
            coverage[
                "sellability"
            ] = True

            confidence += (
                UNIFIED_CONFIDENCE_SELLABILITY_WEIGHT
            )

        evidence = trap_risk.get(
            "evidence",
            {},
        )

        if any(
            key in evidence
            for key in (
                "buy_tax",
                "sell_tax",
                "transfer_tax",
                "round_trip_tax",
            )
        ):
            coverage["tax"] = True

            confidence += (
                UNIFIED_CONFIDENCE_TAX_WEIGHT
            )

        if (
            mev_risk.get("status")
            not in (
                None,
                "UNKNOWN",
            )
        ):
            coverage["mev"] = True

            confidence += (
                UNIFIED_CONFIDENCE_MEV_WEIGHT
            )

        return (
            _clamp(confidence),
            coverage,
        )

    def evaluate(
        self,
        *,
        strategy,
        risk_gate,
        trap_risk,
        mev_risk,
    ):
        (
            strategy_raw,
            opportunity_score,
        ) = self._strategy_score(
            strategy
        )

        (
            tax_penalty,
            tax_details,
            tax_evidence,
        ) = self._tax_penalty(
            trap_risk
        )

        (
            mev_penalty,
            mev_details,
        ) = self._mev_penalty(
            mev_risk
        )

        total_penalty = (
            tax_penalty
            + mev_penalty
        )

        unified_score = _clamp(
            opportunity_score
            - total_penalty
        )

        (
            confidence,
            coverage,
        ) = self._confidence(
            risk_gate,
            trap_risk,
            mev_risk,
        )

        hard_block = bool(
            (risk_gate or {}).get(
                "hard_block"
            )
        )

        return {
            "model": (
                "unified_score_v1"
            ),

            # Existing score normalized to 0-100.
            "legacy_strategy_raw": (
                strategy_raw
            ),
            "opportunity_score": (
                opportunity_score
            ),

            # New independent dimensions.
            "tax_penalty": tax_penalty,
            "mev_penalty": mev_penalty,
            "total_penalty": (
                total_penalty
            ),

            "score": unified_score,

            # Confidence is evidence coverage,
            # NOT probability of winning.
            "confidence": confidence,
            "coverage": coverage,

            "penalty_details": (
                tax_details
                + mev_details
            ),

            "tax_evidence": (
                tax_evidence
            ),

            # Constitutional boundary.
            "hard_block": hard_block,
            "trade_authority": False,

            # v1 is advisory only.
            "decision_authority": False,
        }
