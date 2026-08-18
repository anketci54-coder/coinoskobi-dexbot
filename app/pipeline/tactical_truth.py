def _number(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio_reward_to_risk(
    *,
    entry_price,
    take_profit_price,
    stop_loss_price,
):
    entry = _number(entry_price)
    tp = _number(take_profit_price)
    sl = _number(stop_loss_price)
    if (
        entry is None
        or tp is None
        or sl is None
        or entry <= 0
        or tp <= entry
        or sl >= entry
        or sl <= 0
    ):
        return None
    risk = entry - sl
    return None if risk <= 0 else (tp - entry) / risk


def build_tactical_truth(
    *,
    market_context=None,
    execution_cost=None,
    paper=None,
    tp_multiplier=None,
    sl_multiplier=None,
):
    """Compose runtime tactical truth without fixed TP/SL authority.

    Multiplier arguments are retained only for compatibility with older
    callers and deliberately ignored. Dynamic trade control owns levels.
    """
    market = dict(market_context or {})
    execution = dict(execution_cost or {})
    paper_data = dict(paper or {})

    price = _number(market.get("price_usd"))
    if price is None:
        price = _number(paper_data.get("entry_price"))

    take_profit_price = _number(paper_data.get("tp_price"))
    stop_loss_price = _number(
        paper_data.get("sl_price")
        if paper_data.get("sl_price") is not None
        else paper_data.get("protection_price")
    )

    risk_reward = _ratio_reward_to_risk(
        entry_price=price,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
    )

    entry_plan = {
        "entry_price": price,
        "source": (
            "RUNTIME_MARKET_CONTEXT"
            if _number(market.get("price_usd")) is not None
            else (
                "PAPER_ENTRY_PRICE"
                if _number(paper_data.get("entry_price")) is not None
                else "UNKNOWN"
            )
        ),
    }

    exit_plan = {
        "take_profit_price": take_profit_price,
        "stop_loss_price": stop_loss_price,
        "static_multiplier_authority": False,
        "runner_authority": "HYBRID_DYNAMIC_CONTROLLER",
    }

    expected_pnl = {
        "gross_edge_pct": _number(execution.get("expected_gross_edge_pct")),
        "known_total_cost_pct": _number(execution.get("known_total_cost_pct")),
        "net_expected_pnl_pct": _number(execution.get("net_edge_pct")),
        "source_model": execution.get("model"),
        "feasibility": execution.get("feasibility"),
        "cost_complete": bool(execution.get("cost_complete", False)),
    }

    return {
        "contract": "phase14_tactical_truth_v1",
        "entry_plan": entry_plan,
        "exit_plan": exit_plan,
        "risk_reward": {
            "reward_to_risk": risk_reward,
            "available": risk_reward is not None,
        },
        "expected_pnl": expected_pnl,
        "bounded": True,
        "deterministic": True,
        "read_only": True,
        "proposal_only": True,
        "hot_path_wait": False,
        "provider_call": False,
        "external_fetch": False,
        "ai_inference": False,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
        "hardblock_override_authority": False,
    }
