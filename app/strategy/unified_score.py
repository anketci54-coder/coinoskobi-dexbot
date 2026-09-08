import math


class UnifiedScoreEngine:
    """
    Canonical opportunity readmodel.

    The old evidence-completeness score is retained only as a compatibility
    diagnostic. Entry selection is driven by the observed active continuation
    state, never by completeness percentage.

    Missing evidence is WATCH, not REJECT. Confirmed hard-risk facts remain the
    only rejection authority outside structural impossibility.
    """

    @staticmethod
    def _number(value):
        try:
            if value is None:
                return None
            value = float(value)
        except (TypeError, ValueError):
            return None

        return value if math.isfinite(value) else None

    @classmethod
    def _positive_prices(cls, values):
        out = []
        for value in values or ():
            number = cls._number(value)
            if number is not None and number > 0:
                out.append(number)
        return out

    @classmethod
    def _opportunity_state(cls, *, strategy, risk_gate, mev_risk):
        if risk_gate.get("hard_block"):
            return {
                "state": "REJECT",
                "reason": "CONFIRMED_HARD_RISK",
            }

        if strategy.get("decision") == "REJECT":
            return {
                "state": "REJECT",
                "reason": "STRUCTURAL_REJECT",
            }

        if strategy.get("decision") != "PAPER_BUY":
            return {
                "state": "WATCH",
                "reason": "STRUCTURAL_EVIDENCE_NOT_READY",
            }

        local = risk_gate.get("local_evidence") or {}
        exit_data = local.get("exit_feasibility") or {}
        prices = cls._positive_prices(
            exit_data.get("spot_price_series_usd")
        )

        if len(prices) < 3:
            return {
                "state": "WATCH",
                "reason": "ACTIVE_PRICE_SERIES_NOT_READY",
                "price_observations": len(prices),
            }

        previous_return = math.log(prices[-2] / prices[-3])
        latest_return = math.log(prices[-1] / prices[-2])
        acceleration = latest_return - previous_return

        trailing_positive = []
        for left, right in reversed(list(zip(prices, prices[1:]))):
            value = math.log(right / left)
            if value <= 0:
                break
            trailing_positive.append(value)

        reserve_change = cls._number(
            exit_data.get("reserve_change_fraction")
        )
        quote_reserve = cls._number(
            exit_data.get("quote_reserve_usd")
        )
        mev_status = str(
            mev_risk.get("status") or "UNKNOWN"
        ).upper()

        diagnostics = {
            "price_observations": len(prices),
            "previous_log_return": previous_return,
            "latest_log_return": latest_return,
            "price_acceleration": acceleration,
            "trailing_positive_return_count": len(trailing_positive),
            "trailing_positive_log_move": (
                sum(trailing_positive)
                if trailing_positive
                else 0.0
            ),
            "reserve_change_fraction": reserve_change,
            "quote_reserve_usd": quote_reserve,
            "mev_status": mev_status,
        }

        if latest_return <= 0:
            return {
                "state": "WATCH",
                "reason": "ACTIVE_MOMENTUM_NOT_POSITIVE",
                **diagnostics,
            }

        if acceleration < 0:
            return {
                "state": "WATCH",
                "reason": "ACTIVE_MOMENTUM_DECELERATING",
                **diagnostics,
            }

        if not trailing_positive:
            return {
                "state": "WATCH",
                "reason": "POSITIVE_CONTINUATION_NOT_ESTABLISHED",
                **diagnostics,
            }

        if quote_reserve is None or quote_reserve <= 0:
            return {
                "state": "WATCH",
                "reason": "EXECUTABLE_LIQUIDITY_NOT_READY",
                **diagnostics,
            }

        # On token/WBNB pairs a positive WBNB reserve change is direct onchain
        # confirmation that quote asset is entering the pool while the target
        # price advances. It prevents price-only early admission when flow
        # evidence is incomplete, without inventing a fixed percentage gate.
        if reserve_change is None:
            return {
                "state": "WATCH",
                "reason": "QUOTE_FLOW_CONFIRMATION_NOT_READY",
                **diagnostics,
            }

        if reserve_change <= 0:
            return {
                "state": "WATCH",
                "reason": "QUOTE_FLOW_NOT_SUPPORTING_MOVE",
                **diagnostics,
            }

        if mev_status == "HIGH_EXPOSURE":
            return {
                "state": "WATCH",
                "reason": "EXECUTION_EXPOSURE_HIGH",
                **diagnostics,
            }

        return {
            "state": "HOT",
            "reason": "ACTIVE_CONTINUATION_READY",
            **diagnostics,
        }

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

        trap_evidence = trap_risk.get("evidence") or {}
        sellability = risk_gate.get("sellability", "UNKNOWN")
        honeypot = risk_gate.get("honeypot", "UNKNOWN")
        mev_status = mev_risk.get("status", "UNKNOWN")

        coverage = {
            "strategy": strategy.get("decision") is not None,
            "sellability": sellability in {"SELLABLE", "UNSELLABLE"},
            "honeypot": honeypot in {"YES", "NO"},
            "tax": any(
                trap_evidence.get(key) is not None
                for key in ("buy_tax", "sell_tax", "round_trip_tax")
            ),
            "mev": mev_status not in {None, "UNKNOWN"},
            "local_market": bool(risk_gate.get("local_evidence_complete")),
        }

        known = sum(1 for value in coverage.values() if value)
        coverage_score = 100.0 * known / len(coverage)
        opportunity = self._opportunity_state(
            strategy=strategy,
            risk_gate=risk_gate,
            mev_risk=mev_risk,
        )

        return {
            "model": "unified_score_v1",
            "score": coverage_score,
            "confidence": coverage_score,
            "opportunity_score": None,
            "opportunity_state": opportunity.get("state"),
            "opportunity_reason": opportunity.get("reason"),
            "opportunity": opportunity,
            "score_meaning": "EVIDENCE_COVERAGE_DIAGNOSTIC_ONLY",
            "score_formula": (
                "100*known_evidence_dimensions/declared_evidence_dimensions"
            ),
            "score_authority": False,
            "coverage": coverage,
            "strategy_decision": strategy.get("decision"),
            "structural_ready": bool(strategy.get("structural_ready")),
            "sellability": sellability,
            "honeypot": honeypot,
            "local_evidence_complete": bool(
                risk_gate.get("local_evidence_complete")
            ),
            "hard_block": bool(risk_gate.get("hard_block")),
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
