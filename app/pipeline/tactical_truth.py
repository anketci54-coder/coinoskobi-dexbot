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

    reward = tp - entry
    risk = entry - sl

    if risk <= 0:
        return None

    return reward / risk


def build_tactical_truth(
    *,
    market_context=None,
    execution_cost=None,
    paper=None,
    tp_multiplier=None,
    sl_multiplier=None,
):
    """
    Phase 14 deterministic tactical truth producer.

    Composes existing runtime truth only.

    It does not:
    - make trade decisions
    - open paper/live positions
    - call providers
    - perform external fetches
    - perform AI inference
    - override hard blocks
    """
    market = dict(market_context or {})
    execution = dict(execution_cost or {})
    paper_data = dict(paper or {})

    price = _number(
        market.get("price_usd")
    )

    if price is None:
        price = _number(
            paper_data.get("entry_price")
        )

    tp_mult = _number(tp_multiplier)
    sl_mult = _number(sl_multiplier)

    take_profit_price = None
    stop_loss_price = None

    if (
        price is not None
        and price > 0
        and tp_mult is not None
        and tp_mult > 0
    ):
        take_profit_price = (
            price * tp_mult
        )

    if (
        price is not None
        and price > 0
        and sl_mult is not None
        and sl_mult > 0
    ):
        stop_loss_price = (
            price * sl_mult
        )

    risk_reward = _ratio_reward_to_risk(
        entry_price=price,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
    )

    net_edge_pct = _number(
        execution.get("net_edge_pct")
    )

    expected_gross_edge_pct = _number(
        execution.get(
            "expected_gross_edge_pct"
        )
    )

    known_total_cost_pct = _number(
        execution.get(
            "known_total_cost_pct"
        )
    )

    entry_plan = {
        "entry_price": price,
        "source": (
            "RUNTIME_MARKET_CONTEXT"
            if _number(
                market.get("price_usd")
            ) is not None
            else (
                "PAPER_ENTRY_PRICE"
                if _number(
                    paper_data.get(
                        "entry_price"
                    )
                ) is not None
                else "UNKNOWN"
            )
        ),
    }

    exit_plan = {
        "take_profit_price": (
            take_profit_price
        ),
        "stop_loss_price": (
            stop_loss_price
        ),
        "tp_multiplier": tp_mult,
        "sl_multiplier": sl_mult,
    }

    expected_pnl = {
        "gross_edge_pct": (
            expected_gross_edge_pct
        ),
        "known_total_cost_pct": (
            known_total_cost_pct
        ),
        "net_expected_pnl_pct": (
            net_edge_pct
        ),
        "source_model": (
            execution.get("model")
        ),
        "feasibility": (
            execution.get("feasibility")
        ),
        "cost_complete": bool(
            execution.get(
                "cost_complete",
                False,
            )
        ),
    }

    return {
        "contract": (
            "phase14_tactical_truth_v1"
        ),

        "entry_plan": entry_plan,
        "exit_plan": exit_plan,

        "risk_reward": {
            "reward_to_risk": risk_reward,
            "available": (
                risk_reward is not None
            ),
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
