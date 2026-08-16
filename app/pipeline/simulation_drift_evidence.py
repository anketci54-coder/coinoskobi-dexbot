from datetime import datetime, timezone


def _number(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_ms(start, end):
    if not start or not end:
        return None
    try:
        a = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return max(0.0, (b - a).total_seconds() * 1000.0)


def build_phase15_execution_evidence(*, paper_position=None, runtime_evidence=None):
    """Bind existing paper/runtime facts into Phase 15 drift inputs.

    Pure-local evidence adapter: it performs no provider fetch, wallet use,
    signing, execution, or authority grant. Missing facts remain None.
    """
    paper = dict(paper_position or {})
    runtime = dict(runtime_evidence or {})

    entry = _number(paper.get("entry_price"))
    exit_price = _number(paper.get("exit_price"))
    slippage = _number(paper.get("slippage"))
    gas_buy = _number(paper.get("gas_buy"))
    gas_sell = _number(paper.get("gas_sell"))
    net_pnl = _number(paper.get("net_pnl"))

    net_pnl_pct = None
    if entry not in (None, 0.0) and net_pnl is not None:
        # Paper DB stores realized PnL as an amount. Percentage is only
        # derivable when a compatible notional is explicitly supplied.
        notional = _number(paper.get("trade_value"))
        if notional not in (None, 0.0):
            net_pnl_pct = (net_pnl / notional) * 100.0

    paper_execution = {
        "entry_price": entry,
        "exit_price": exit_price,
        "slippage_pct": slippage,
        "gas_cost_usd": None,
        "mev_cost_pct": None,
        "quote_delay_ms": None,
        "execution_delay_ms": None,
        "net_pnl_pct": net_pnl_pct,
        "liquidity_usd": _number(paper.get("liquidity_usd")),
        "sellability": paper.get("sellability"),
    }

    # gas_buy/gas_sell are retained as native paper evidence; they are not
    # mislabeled USD without a conversion fact.
    paper_native = {
        "gas_buy": gas_buy,
        "gas_sell": gas_sell,
        "net_pnl": net_pnl,
        "opened_at": paper.get("created_at") or paper.get("opened_at"),
        "closed_at": paper.get("closed_at"),
    }

    observed_execution = {
        "entry_price": _number(runtime.get("entry_price")),
        "exit_price": _number(runtime.get("exit_price")),
        "slippage_pct": _number(runtime.get("slippage_pct")),
        "gas_cost_usd": _number(runtime.get("gas_cost_usd")),
        "mev_cost_pct": _number(runtime.get("mev_cost_pct")),
        "quote_delay_ms": _number(runtime.get("quote_delay_ms")),
        "execution_delay_ms": _number(runtime.get("execution_delay_ms")),
        "net_pnl_pct": _number(runtime.get("net_pnl_pct")),
        "liquidity_usd": _number(runtime.get("liquidity_usd")),
        "sellability": runtime.get("sellability"),
    }

    if observed_execution["execution_delay_ms"] is None:
        observed_execution["execution_delay_ms"] = _iso_ms(
            runtime.get("execution_started_at"),
            runtime.get("execution_observed_at"),
        )

    available = sum(
        value is not None
        for value in observed_execution.values()
    )

    return {
        "contract": "phase15_execution_evidence_v1",
        "paper_execution": paper_execution,
        "paper_native_evidence": paper_native,
        "observed_execution": observed_execution,
        "observed_evidence_count": available,
        "observed_evidence_complete": available >= 5,
        "missing_observed_fields": [
            key for key, value in observed_execution.items()
            if value is None
        ],
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
