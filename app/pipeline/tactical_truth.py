def _number(value):
    try:
        if value is None:
            return None

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _ratio_reward_to_risk(
    *,
    entry_price,
    take_profit_price,
    stop_loss_price,
):
    entry = _number(
        entry_price
    )

    tp = _number(
        take_profit_price
    )

    sl = _number(
        stop_loss_price
    )

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

    risk = (
        entry
        - sl
    )

    return (
        (
            tp - entry
        )
        / risk
        if risk > 0
        else None
    )


def build_tactical_truth(
    *,
    market_context=None,
    execution_cost=None,
    paper=None,
    tp_multiplier=None,
    sl_multiplier=None,
    mathematical_plan=None,
):
    market = dict(
        market_context
        or {}
    )

    execution = dict(
        execution_cost
        or {}
    )

    paper_data = dict(
        paper
        or {}
    )

    plan = dict(
        mathematical_plan
        or {}
    )

    if (
        plan.get(
            "contract"
        )
        == (
            "mathematical_trade_plan"
        )
    ):
        entry = (
            plan.get(
                "entry"
            )
            or {}
        )

        sl = (
            plan.get(
                "sl"
            )
            or {}
        )

        tp1 = (
            plan.get(
                "tp1"
            )
            or {}
        )

        tp2 = (
            plan.get(
                "tp2"
            )
            or {}
        )

        runner = (
            plan.get(
                "runner"
            )
            or {}
        )

        expected = (
            plan.get(
                "expected"
            )
            or {}
        )

        capital = (
            plan.get(
                "capital"
            )
            or {}
        )

        position = (
            plan.get(
                "position"
            )
            or {}
        )

        return {
            "contract": (
                "phase14_tactical_truth_mathematical"
            ),

            "entry_plan": {
                "entry_price": (
                    entry.get(
                        "price"
                    )
                ),

                "entry_band_low": (
                    entry.get(
                        "band_low"
                    )
                ),

                "entry_band_high": (
                    entry.get(
                        "band_high"
                    )
                ),

                "capital_usdt": (
                    capital.get(
                        "entry_amount_usdt"
                    )
                ),

                "position_fraction_of_available": (
                    capital.get(
                        "position_fraction_of_available"
                    )
                ),

                "source": (
                    "MATHEMATICAL_TRADE_PLAN"
                ),
            },

            "exit_plan": {
                "initial_stop_loss_price": (
                    sl.get(
                        "initial_price"
                    )
                ),

                "current_stop_loss_price": (
                    paper_data.get(
                        "sl_price"
                    )
                    or sl.get(
                        "initial_price"
                    )
                ),

                "tp1_activation_price": (
                    tp1.get(
                        "activation_price"
                    )
                ),

                "tp1_static_fraction": None,

                "tp1_realization_rule": (
                    tp1.get(
                        "realization_rule"
                    )
                ),

                "tp2_activation_price": (
                    tp2.get(
                        "activation_price"
                    )
                ),

                "tp2_static_fraction": None,

                "tp2_realization_rule": (
                    tp2.get(
                        "realization_rule"
                    )
                ),

                "tp3_static_price": None,

                "runner_rule": (
                    runner.get(
                        "rule"
                    )
                ),
            },

            "risk_reward": {
                "initial_risk_usdt": (
                    position.get(
                        "initial_risk_usdt"
                    )
                ),

                "reward_to_risk": None,

                "available": False,

                "reason": (
                    "NO_FIXED_TP_REWARD_RATIO_"
                    "IN_DYNAMIC_RUNNER_MODEL"
                ),
            },

            "expected_pnl": {
                "known_net_edge_fraction": (
                    expected.get(
                        "known_net_edge_fraction"
                    )
                ),

                "full_net_edge_fraction": (
                    expected.get(
                        "full_net_edge_fraction"
                    )
                ),

                "cost_complete": bool(
                    (
                        plan.get(
                            "cost_model"
                        )
                        or {}
                    ).get(
                        "cost_complete"
                    )
                ),

                "semantics": (
                    (
                        plan.get(
                            "cost_model"
                        )
                        or {}
                    ).get(
                        "net_semantics"
                    )
                ),
            },

            "mathematical_score": (
                plan.get(
                    "score"
                )
            ),

            "blockers": (
                plan.get(
                    "blockers",
                    [],
                )
            ),

            "unknowns": (
                plan.get(
                    "unknowns",
                    [],
                )
            ),

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

    # Historical/legacy readmodel fallback.
    price = _number(
        market.get(
            "price_usd"
        )
    )

    if price is None:
        price = _number(
            paper_data.get(
                "entry_price"
            )
        )

    tp_mult = _number(
        tp_multiplier
    )

    sl_mult = _number(
        sl_multiplier
    )

    take_profit_price = (
        price
        * tp_mult
        if (
            price
            and tp_mult
            and tp_mult > 0
        )
        else None
    )

    stop_loss_price = (
        price
        * sl_mult
        if (
            price
            and sl_mult
            and sl_mult > 0
        )
        else None
    )

    risk_reward = (
        _ratio_reward_to_risk(
            entry_price=price,

            take_profit_price=(
                take_profit_price
            ),

            stop_loss_price=(
                stop_loss_price
            ),
        )
    )

    return {
        "contract": (
            "phase14_tactical_truth_v1"
        ),

        "entry_plan": {
            "entry_price": price,

            "source": (
                "RUNTIME_MARKET_CONTEXT"
                if _number(
                    market.get(
                        "price_usd"
                    )
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
        },

        "exit_plan": {
            "take_profit_price": (
                take_profit_price
            ),

            "stop_loss_price": (
                stop_loss_price
            ),

            "tp_multiplier": (
                tp_mult
            ),

            "sl_multiplier": (
                sl_mult
            ),
        },

        "risk_reward": {
            "reward_to_risk": (
                risk_reward
            ),

            "available": (
                risk_reward
                is not None
            ),
        },

        "expected_pnl": {
            "gross_edge_pct": (
                _number(
                    execution.get(
                        "expected_gross_edge_pct"
                    )
                )
            ),

            "known_total_cost_pct": (
                _number(
                    execution.get(
                        "known_total_cost_pct"
                    )
                )
            ),

            "net_expected_pnl_pct": (
                _number(
                    execution.get(
                        "net_edge_pct"
                    )
                )
            ),

            "source_model": (
                execution.get(
                    "model"
                )
            ),

            "feasibility": (
                execution.get(
                    "feasibility"
                )
            ),

            "cost_complete": bool(
                execution.get(
                    "cost_complete",
                    False,
                )
            ),
        },

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
