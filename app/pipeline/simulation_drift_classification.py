def _number(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_RANK = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def _severity(value, *, low, medium, high, critical):
    value = _number(value)

    if value is None:
        return None

    # Improvement / zero deterioration is not harmful drift.
    if value <= 0:
        return "NONE"

    if value >= critical:
        return "CRITICAL"
    if value >= high:
        return "HIGH"
    if value >= medium:
        return "MEDIUM"
    if value >= low:
        return "LOW"

    return "NONE"


def _strongest(severities):
    strongest = "NONE"

    for severity in severities:
        if severity is None:
            continue

        if _RANK.get(severity, 0) > _RANK[strongest]:
            strongest = severity

    return strongest


def _delta(drift, field):
    return _number(
        dict(drift.get(field) or {}).get("delta")
    )


def classify_simulation_drift(
    simulation_drift=None,
):
    """
    Phase 15F deterministic simulation-drift classification.

    Classification/readmodel only.

    It does NOT:
    - create a RiskGate hard block
    - alter paper admission
    - alter execution behavior
    - grant decision/execution authority

    UNKNOWN and INSUFFICIENT_EVIDENCE are evidence states,
    not harmful drift classifications.
    """

    source = dict(simulation_drift or {})

    comparison_complete = bool(
        source.get("comparison_complete", False)
    )

    comparable_count = int(
        source.get("comparable_evidence_count", 0)
        or 0
    )

    if not source:
        state = "UNKNOWN"
    elif not comparison_complete:
        state = "INSUFFICIENT_EVIDENCE"
    else:
        state = "CLASSIFIED"

    drift = dict(source.get("drift") or {})
    liquidity = dict(source.get("liquidity") or {})
    sellability = dict(source.get("sellability") or {})

    liquidity_paper = _number(
        liquidity.get("paper_usd")
    )
    liquidity_observed = _number(
        liquidity.get("observed_usd")
    )

    liquidity_drop_pct = None

    if (
        liquidity_paper is not None
        and liquidity_paper > 0
        and liquidity_observed is not None
    ):
        liquidity_drop_pct = (
            (
                liquidity_paper
                - liquidity_observed
            )
            / liquidity_paper
        ) * 100.0

    metrics = {
        "slippage_pct": {
            "deterioration": _delta(
                drift,
                "slippage_pct",
            ),
            "severity": _severity(
                _delta(drift, "slippage_pct"),
                low=0.25,
                medium=0.75,
                high=1.50,
                critical=3.00,
            ),
        },
        "mev_cost_pct": {
            "deterioration": _delta(
                drift,
                "mev_cost_pct",
            ),
            "severity": _severity(
                _delta(drift, "mev_cost_pct"),
                low=0.10,
                medium=0.30,
                high=0.75,
                critical=1.50,
            ),
        },
        "quote_delay_ms": {
            "deterioration": _delta(
                drift,
                "quote_delay_ms",
            ),
            "severity": _severity(
                _delta(drift, "quote_delay_ms"),
                low=100,
                medium=300,
                high=750,
                critical=1500,
            ),
        },
        "execution_delay_ms": {
            "deterioration": _delta(
                drift,
                "execution_delay_ms",
            ),
            "severity": _severity(
                _delta(drift, "execution_delay_ms"),
                low=150,
                medium=500,
                high=1000,
                critical=2500,
            ),
        },
        "net_pnl_pct": {
            # Negative PnL delta means observed result was worse.
            "deterioration": (
                -_delta(drift, "net_pnl_pct")
                if _delta(drift, "net_pnl_pct")
                is not None
                else None
            ),
            "severity": _severity(
                (
                    -_delta(drift, "net_pnl_pct")
                    if _delta(drift, "net_pnl_pct")
                    is not None
                    else None
                ),
                low=0.50,
                medium=1.50,
                high=3.00,
                critical=5.00,
            ),
        },
        "liquidity_drop_pct": {
            "deterioration": liquidity_drop_pct,
            "severity": _severity(
                liquidity_drop_pct,
                low=5.0,
                medium=10.0,
                high=20.0,
                critical=40.0,
            ),
        },
    }

    if state != "CLASSIFIED":
        severity = None
        classification = state
    else:
        severity = _strongest(
            metric.get("severity")
            for metric in metrics.values()
        )
        classification = (
            "NO_DRIFT"
            if severity == "NONE"
            else f"{severity}_DRIFT"
        )

    return {
        "contract": (
            "phase15_drift_classification_v1"
        ),
        "state": state,
        "classification": classification,
        "severity": severity,
        "comparison_complete": comparison_complete,
        "comparable_evidence_count": comparable_count,
        "metrics": metrics,
        "sellability_changed": (
            sellability.get("changed")
        ),

        # Classification is intentionally not a blocker.
        "blocks_trade": False,
        "blocks_paper": False,
        "risk_gate_binding": False,
        "observation_only": True,
        "bounded": True,
        "deterministic": True,

        "provider_call": False,
        "external_fetch": False,
        "wallet_use": False,
        "signing": False,
        "executed": False,

        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
        "hardblock_override_authority": False,
    }
