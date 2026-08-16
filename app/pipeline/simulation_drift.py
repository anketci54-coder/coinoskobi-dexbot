def _number(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(paper_value, observed_value):
    paper_value = _number(paper_value)
    observed_value = _number(observed_value)

    if paper_value is None or observed_value is None:
        return None

    return observed_value - paper_value


def build_simulation_drift(
    *,
    paper_execution=None,
    observed_execution=None,
):
    """
    Phase 15 simulation-drift validator.

    Compares paper execution assumptions with supplied observed
    execution evidence.

    Evidence/readmodel only:
    - no provider fetch
    - no wallet/signing
    - no trade execution
    - no authority grant
    """

    paper = dict(paper_execution or {})
    observed = dict(observed_execution or {})

    fields = (
        "entry_price",
        "exit_price",
        "slippage_pct",
        "gas_cost_usd",
        "mev_cost_pct",
        "quote_delay_ms",
        "execution_delay_ms",
    )

    drift = {}

    comparable = 0

    for field in fields:
        paper_value = _number(
            paper.get(field)
        )
        observed_value = _number(
            observed.get(field)
        )

        delta = _delta(
            paper_value,
            observed_value,
        )

        if delta is not None:
            comparable += 1

        drift[field] = {
            "paper": paper_value,
            "observed": observed_value,
            "delta": delta,
        }

    paper_pnl = _number(
        paper.get("net_pnl_pct")
    )
    observed_pnl = _number(
        observed.get("net_pnl_pct")
    )

    pnl_delta = _delta(
        paper_pnl,
        observed_pnl,
    )

    if pnl_delta is not None:
        comparable += 1

    drift["net_pnl_pct"] = {
        "paper": paper_pnl,
        "observed": observed_pnl,
        "delta": pnl_delta,
    }

    sellability_changed = None

    paper_sellability = paper.get(
        "sellability"
    )
    observed_sellability = observed.get(
        "sellability"
    )

    if (
        paper_sellability is not None
        and observed_sellability is not None
    ):
        sellability_changed = (
            paper_sellability
            != observed_sellability
        )
        comparable += 1

    liquidity_delta = _delta(
        paper.get("liquidity_usd"),
        observed.get("liquidity_usd"),
    )

    if liquidity_delta is not None:
        comparable += 1

    complete = comparable >= 5

    return {
        "contract": (
            "phase15_simulation_drift_v1"
        ),
        "paper_execution": paper,
        "observed_execution": observed,
        "drift": drift,
        "liquidity": {
            "paper_usd": _number(
                paper.get("liquidity_usd")
            ),
            "observed_usd": _number(
                observed.get("liquidity_usd")
            ),
            "delta_usd": liquidity_delta,
        },
        "sellability": {
            "paper": paper_sellability,
            "observed": observed_sellability,
            "changed": sellability_changed,
        },
        "comparable_evidence_count": comparable,
        "comparison_complete": complete,

        # Phase 15A remains evidence-only.
        "read_only": True,
        "observation_only": True,
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
