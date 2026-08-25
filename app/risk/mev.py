from app.config.risk import (
    MEV_LIQUIDITY_CAUTION_USD,
    MEV_LIQUIDITY_HIGH_RISK_USD,
    MEV_PRICE_IMPACT_CAUTION_PERCENT,
    MEV_PRICE_IMPACT_CRITICAL_PERCENT,
    MEV_PRICE_IMPACT_HIGH_PERCENT,
    MEV_SLIPPAGE_CAUTION_PERCENT,
    MEV_SLIPPAGE_CRITICAL_PERCENT,
    MEV_SLIPPAGE_HIGH_PERCENT,
    MEV_TRADE_LIQUIDITY_CAUTION_PERCENT,
    MEV_TRADE_LIQUIDITY_CRITICAL_PERCENT,
    MEV_TRADE_LIQUIDITY_HIGH_PERCENT,
)


def _number(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if value < 0:
        return None

    return value


def expected_mev_loss(
    attack_probability,
    conditional_loss_usd,
):
    """
    Evidence-bound expected MEV loss.

    E[MEV loss] = P(attack) * E[loss | attack]

    No probability is inferred here. The probability must come from a
    calibrated model or measured empirical estimator, and the conditional
    loss must come from an execution/sandwich loss model.
    """
    probability = _number(
        attack_probability
    )
    conditional_loss = _number(
        conditional_loss_usd
    )

    if (
        probability is None
        or conditional_loss is None
        or probability > 1.0
    ):
        return {
            "state": "UNKNOWN",
            "attack_probability": None,
            "conditional_loss_usd": None,
            "expected_mev_loss_usd": None,
            "decision_authority": False,
            "trade_authority": False,
        }

    return {
        "state": "READY",
        "attack_probability": probability,
        "conditional_loss_usd": conditional_loss,
        "expected_mev_loss_usd": (
            probability
            * conditional_loss
        ),
        "decision_authority": False,
        "trade_authority": False,
    }


class MEVExposureAnalyzer:
    """
    Pure-local MEV / sandwich exposure model.

    Bu katman:
    - bot tespit ettigini iddia etmez
    - RPC yapmaz
    - HTTP yapmaz
    - trade karari vermez
    - hard-block yetkisine sahip degildir

    Yalniz mevcut market/execution verisinden
    exposure sinyali uretir.
    """

    def evaluate(self, context):
        context = context or {}

        liquidity_usd = _number(
            context.get("liquidity_usd")
        )

        trade_size_usd = _number(
            context.get("trade_size_usd")
        )

        price_impact_pct = _number(
            context.get("price_impact_pct")
        )

        slippage_pct = _number(
            context.get("slippage_pct")
        )

        signals = []
        evidence = {}

        if liquidity_usd is not None:
            evidence[
                "liquidity_usd"
            ] = liquidity_usd

            if (
                liquidity_usd
                < MEV_LIQUIDITY_HIGH_RISK_USD
            ):
                signals.append({
                    "code": "SHALLOW_LIQUIDITY_HIGH",
                    "severity": "HIGH",
                    "value": liquidity_usd,
                })

            elif (
                liquidity_usd
                < MEV_LIQUIDITY_CAUTION_USD
            ):
                signals.append({
                    "code": "SHALLOW_LIQUIDITY",
                    "severity": "MEDIUM",
                    "value": liquidity_usd,
                })

        trade_liquidity_pct = None

        if (
            liquidity_usd is not None
            and liquidity_usd > 0
            and trade_size_usd is not None
        ):
            trade_liquidity_pct = (
                trade_size_usd
                / liquidity_usd
                * 100
            )

            evidence[
                "trade_size_usd"
            ] = trade_size_usd

            evidence[
                "trade_liquidity_pct"
            ] = trade_liquidity_pct

            if (
                trade_liquidity_pct
                >= MEV_TRADE_LIQUIDITY_CRITICAL_PERCENT
            ):
                signals.append({
                    "code": (
                        "TRADE_LIQUIDITY_RATIO_CRITICAL"
                    ),
                    "severity": "CRITICAL",
                    "value": trade_liquidity_pct,
                })

            elif (
                trade_liquidity_pct
                >= MEV_TRADE_LIQUIDITY_HIGH_PERCENT
            ):
                signals.append({
                    "code": (
                        "TRADE_LIQUIDITY_RATIO_HIGH"
                    ),
                    "severity": "HIGH",
                    "value": trade_liquidity_pct,
                })

            elif (
                trade_liquidity_pct
                >= MEV_TRADE_LIQUIDITY_CAUTION_PERCENT
            ):
                signals.append({
                    "code": (
                        "TRADE_LIQUIDITY_RATIO_ELEVATED"
                    ),
                    "severity": "MEDIUM",
                    "value": trade_liquidity_pct,
                })

        def classify_percent(
            name,
            value,
            caution,
            high,
            critical,
        ):
            if value is None:
                return

            evidence[name] = value

            if value >= critical:
                severity = "CRITICAL"
                suffix = "CRITICAL"

            elif value >= high:
                severity = "HIGH"
                suffix = "HIGH"

            elif value >= caution:
                severity = "MEDIUM"
                suffix = "ELEVATED"

            elif value > 0:
                severity = "LOW"
                suffix = "LOW"

            else:
                return

            signals.append({
                "code": (
                    f"{name.upper()}_{suffix}"
                ),
                "severity": severity,
                "value": value,
            })

        classify_percent(
            "price_impact_pct",
            price_impact_pct,
            MEV_PRICE_IMPACT_CAUTION_PERCENT,
            MEV_PRICE_IMPACT_HIGH_PERCENT,
            MEV_PRICE_IMPACT_CRITICAL_PERCENT,
        )

        classify_percent(
            "slippage_pct",
            slippage_pct,
            MEV_SLIPPAGE_CAUTION_PERCENT,
            MEV_SLIPPAGE_HIGH_PERCENT,
            MEV_SLIPPAGE_CRITICAL_PERCENT,
        )

        rank = {
            "NONE": 0,
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
        }

        severity = "NONE"

        for signal in signals:
            candidate = signal[
                "severity"
            ]

            if (
                rank[candidate]
                > rank[severity]
            ):
                severity = candidate

        sufficient_context = any(
            value is not None
            for value in (
                liquidity_usd,
                trade_size_usd,
                price_impact_pct,
                slippage_pct,
            )
        )

        if not sufficient_context:
            status = "UNKNOWN"

        elif severity == "NONE":
            status = "LOW_EXPOSURE"

        elif severity in (
            "LOW",
            "MEDIUM",
        ):
            status = "ELEVATED_EXPOSURE"

        else:
            status = "HIGH_EXPOSURE"

        expected_loss = expected_mev_loss(
            context.get(
                "mev_attack_probability"
            ),
            context.get(
                "mev_conditional_loss_usd"
            ),
        )

        return {
            "status": status,
            "severity": severity,
            "signals": signals,
            "signal_count": len(signals),
            "evidence": evidence,
            "trade_liquidity_pct": (
                trade_liquidity_pct
            ),
            "expected_loss": expected_loss,

            # Constitutional authority boundary.
            "hard_block": False,
            "trade_authority": False,
        }
