from app.config.risk import (
    ROUND_TRIP_TAX_CAUTION_PERCENT,
    ROUND_TRIP_TAX_HIGH_PERCENT,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_NONE,
    TAX_CAUTION_PERCENT,
    TAX_EXTREME_PERCENT,
    TAX_HIGH_PERCENT,
)


def _as_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


class TrapRiskAnalyzer:
    """
    Pure-local risk signal classifier.

    No RPC.
    No HTTP.
    No DB write.
    No trade authority.

    Inputs are evidence already collected by
    bytecode / sellability analyzers.

    UNKNOWN does not become dangerous by default.
    """

    def evaluate(self, risk):
        risk = risk or {}

        signals = []
        evidence = {}

        buy_tax = _as_float(
            risk.get("buy_tax")
        )

        sell_tax = _as_float(
            risk.get("sell_tax")
        )

        transfer_tax = _as_float(
            risk.get("transfer_tax")
        )

        # --------------------------------------------------------
        # CONTRACT CONTROL SIGNALS
        # --------------------------------------------------------

        control_map = (
            (
                "mint",
                "MINT_CAPABILITY",
                "MEDIUM",
            ),
            (
                "pause",
                "PAUSE_CAPABILITY",
                "MEDIUM",
            ),
            (
                "blacklist",
                "BLACKLIST_CAPABILITY",
                "HIGH",
            ),
            (
                "set_blacklist",
                "BLACKLIST_CONTROL",
                "HIGH",
            ),
            (
                "max_tx",
                "MAX_TX_CONTROL",
                "LOW",
            ),
            (
                "max_wallet",
                "MAX_WALLET_CONTROL",
                "LOW",
            ),
        )

        for (
            field,
            code,
            severity,
        ) in control_map:
            if risk.get(field) is True:
                signals.append({
                    "code": code,
                    "severity": severity,
                    "source": "bytecode",
                })

                evidence[field] = True

        # --------------------------------------------------------
        # TAX SIGNALS
        # --------------------------------------------------------

        def add_tax_signal(
            name,
            value,
        ):
            if value is None:
                return

            evidence[name] = value

            if value >= TAX_EXTREME_PERCENT:
                severity = SEVERITY_CRITICAL
                label = "EXTREME"

            elif value >= TAX_HIGH_PERCENT:
                severity = SEVERITY_HIGH
                label = "HIGH"

            elif value >= TAX_CAUTION_PERCENT:
                severity = SEVERITY_MEDIUM
                label = "ELEVATED"

            elif value > 0:
                severity = SEVERITY_LOW
                label = "NONZERO"

            else:
                return

            signals.append({
                "code": (
                    f"{name.upper()}_{label}"
                ),
                "severity": severity,
                "source": "simulation",
                "value": value,
            })

        add_tax_signal(
            "buy_tax",
            buy_tax,
        )

        add_tax_signal(
            "sell_tax",
            sell_tax,
        )

        add_tax_signal(
            "transfer_tax",
            transfer_tax,
        )

        # --------------------------------------------------------
        # ROUND-TRIP COST SIGNAL
        # --------------------------------------------------------

        round_trip_tax = None

        if (
            buy_tax is not None
            and sell_tax is not None
        ):
            round_trip_tax = (
                buy_tax
                + sell_tax
            )

            evidence[
                "round_trip_tax"
            ] = round_trip_tax

            if (
                round_trip_tax
                >= ROUND_TRIP_TAX_HIGH_PERCENT
            ):
                signals.append({
                    "code": (
                        "ROUND_TRIP_TAX_HIGH"
                    ),
                    "severity": (
                        SEVERITY_HIGH
                    ),
                    "source": "simulation",
                    "value": round_trip_tax,
                })

            elif (
                round_trip_tax
                >= ROUND_TRIP_TAX_CAUTION_PERCENT
            ):
                signals.append({
                    "code": (
                        "ROUND_TRIP_TAX_ELEVATED"
                    ),
                    "severity": (
                        SEVERITY_MEDIUM
                    ),
                    "source": "simulation",
                    "value": round_trip_tax,
                })

        # --------------------------------------------------------
        # CONFIRMED SELLABILITY EVIDENCE
        # --------------------------------------------------------

        if risk.get("sellable") is False:
            signals.append({
                "code": "SELL_NOT_POSSIBLE",
                "severity": SEVERITY_CRITICAL,
                "source": "sellability",
            })

        if risk.get("honeypot") is True:
            signals.append({
                "code": "HONEYPOT_CONFIRMED",
                "severity": SEVERITY_CRITICAL,
                "source": "sellability",
            })

        # --------------------------------------------------------
        # AGGREGATE SEVERITY
        # --------------------------------------------------------

        rank = {
            SEVERITY_NONE: 0,
            SEVERITY_LOW: 1,
            SEVERITY_MEDIUM: 2,
            SEVERITY_HIGH: 3,
            SEVERITY_CRITICAL: 4,
        }

        severity = SEVERITY_NONE

        for signal in signals:
            candidate = signal[
                "severity"
            ]

            if (
                rank[candidate]
                > rank[severity]
            ):
                severity = candidate

        if severity == SEVERITY_NONE:
            status = "CLEAR"

        elif severity in (
            SEVERITY_LOW,
            SEVERITY_MEDIUM,
        ):
            status = "CAUTION"

        else:
            status = "HIGH_RISK"

        return {
            "status": status,
            "severity": severity,
            "signals": signals,
            "signal_count": len(signals),
            "evidence": evidence,
            "round_trip_tax": (
                round_trip_tax
            ),

            # This classifier never grants
            # or denies trade authority.
            "trade_authority": False,
            "hard_block": False,
        }
