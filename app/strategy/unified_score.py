import math


class UnifiedScoreEngine:
    """
    Canonical opportunity readmodel.

    Evidence completeness is retained only as a compatibility diagnostic.
    Entry selection is driven by the observed active continuation state,
    never by completeness percentage.

    Missing evidence is not negative evidence. Confirmed hard-risk facts and
    confirmed opposing flow remain authoritative, while incomplete flow stays
    observable instead of permanently suppressing an otherwise valid move.
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
        latest_reserve_change = cls._number(
            exit_data.get("latest_reserve_change_fraction")
        )
        quote_reserve = cls._number(
            exit_data.get("quote_reserve_usd")
        )
        mev_status = str(
            mev_risk.get("status") or "UNKNOWN"
        ).upper()

        quote_flow_state = "UNKNOWN"
        if latest_reserve_change is not None:
            quote_flow_state = (
                "SUPPORTING"
                if latest_reserve_change > 0
                else "OPPOSING"
            )
        elif reserve_change is not None:
            quote_flow_state = (
                "SUPPORTING"
                if reserve_change > 0
                else "OPPOSING"
            )

        flow_delta = (
            latest_reserve_change
            if latest_reserve_change is not None
            else reserve_change
        )

        # A recovery after a sharp drawdown is not continuation by itself.
        # However, when price reclaims the entire prior observed range and
        # quote reserves are still supporting the move, waiting for another
        # green sample systematically adds latency without adding the same
        # protection. This is the early breakout lane. It cannot fire on a
        # simple dead-cat bounce such as [100, 50, 51].
        recovery_breakout = (
            latest_return > 0
            and prices[-1] > max(prices[:-1])
            and flow_delta is not None
            and flow_delta > 0
        )

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
            "recovery_breakout": recovery_breakout,
            "reserve_change_fraction": reserve_change,
            "latest_reserve_change_fraction": latest_reserve_change,
            "quote_flow_state": quote_flow_state,
            "quote_reserve_usd": quote_reserve,
            "mev_status": mev_status,
        }

        if latest_return <= 0:
            return {
                "state": "WATCH",
                "reason": "ACTIVE_MOMENTUM_NOT_POSITIVE",
                **diagnostics,
            }

        # Normal continuation requires two consecutive positive observations.
        # The only exception is a confirmed recovery breakout: current price
        # must reclaim the whole prior observed range and quote flow must still
        # support the move. This avoids turning a dead-cat bounce into an entry.
        if len(trailing_positive) < 2 and not recovery_breakout:
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

        # Recent measured quote outflow is authoritative. If the latest
        # interval is unavailable, fall back to the wider observed interval.
        # Completely missing flow evidence remains UNKNOWN rather than BAD.
        if flow_delta is not None and flow_delta <= 0:
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

        reason = (
            "ACTIVE_RECOVERY_BREAKOUT_READY"
            if recovery_breakout and len(trailing_positive) < 2
            else "ACTIVE_CONTINUATION_READY"
        )

        return {
            "state": "HOT",
            "reason": reason,
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
