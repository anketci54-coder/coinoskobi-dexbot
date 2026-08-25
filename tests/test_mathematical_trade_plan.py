from app.strategy.mathematical_trade_plan import (
    build_trade_plan,
    dynamic_stop_price,
    tp1_required_fraction,
)


def exit_evidence():
    return {
        "route_friction_fraction": 0.0,

        "gas_price_wei": 0,

        "wbnb_usd_estimate": 600.0,
    }


def sellability():
    return {
        "buy_tax": 0,
        "sell_tax": 0,

        "buy_gas": 0,
        "sell_gas": 0,
    }


def test_plan_has_no_static_tp_fraction_or_tp3_price():
    plan = build_trade_plan(
        entry_price=1.04,

        available_capital_usdt=1000,

        price_series=[
            1.0,
            1.02,
            1.04,
        ],

        quote_reserve_usd=10000,

        lp_protected_fraction=1.0,

        sellability_status=(
            "SELLABILITY_OK"
        ),

        sellability_data=(
            sellability()
        ),

        exit_evidence=(
            exit_evidence()
        ),
    )

    assert (
        plan[
            "paper_eligible"
        ]
        is True
    )

    assert (
        plan[
            "capital"
        ][
            "entry_amount_usdt"
        ]
        > 0
    )

    assert (
        plan[
            "tp1"
        ][
            "static_fraction"
        ]
        is None
    )

    assert (
        plan[
            "tp2"
        ][
            "static_fraction"
        ]
        is None
    )

    assert (
        plan[
            "runner"
        ][
            "static_tp_price"
        ]
        is None
    )

    assert (
        plan[
            "score"
        ][
            "decision_threshold"
        ]
        is None
    )


def test_unprotected_lp_naturally_sizes_zero_without_percent_threshold():
    plan = build_trade_plan(
        entry_price=1.04,

        available_capital_usdt=1000,

        price_series=[
            1.0,
            1.02,
            1.04,
        ],

        quote_reserve_usd=10000,

        lp_protected_fraction=0.0,

        sellability_status=(
            "SELLABILITY_UNKNOWN"
        ),

        sellability_data={},

        exit_evidence=(
            exit_evidence()
        ),
    )

    assert (
        plan[
            "paper_eligible"
        ]
        is False
    )

    assert (
        plan[
            "capital"
        ][
            "entry_amount_usdt"
        ]
        == 0
    )

    assert (
        "NO_VERIFIED_PERSISTENT_LIQUIDITY"
        in plan[
            "blockers"
        ]
    )



def test_unprotected_lp_can_use_measured_empirical_reserve_floor():
    plan = build_trade_plan(
        entry_price=1.04,
        available_capital_usdt=1000,
        price_series=[
            1.0,
            1.02,
            1.04,
        ],
        quote_reserve_usd=10000,
        lp_protected_fraction=0.0,
        sellability_status="SELLABILITY_OK",
        sellability_data=sellability(),
        exit_evidence={
            **exit_evidence(),
            "observed_min_quote_reserve_usd": 8000.0,
            "reserve_observation_count": 3,
        },
    )

    blockers = set(plan["blockers"])

    assert "NO_VERIFIED_PERSISTENT_LIQUIDITY" not in blockers
    assert plan["capital"]["safe_quote_reserve_usd"] == 8000.0
    assert (
        plan["capital"]["liquidity_capacity_source"]
        == "EMPIRICAL_RESERVE_FLOOR"
    )
    assert plan["capital"]["entry_amount_usdt"] > 0


def test_unknown_lp_protection_remains_unknown_but_not_veto_with_empirical_floor():
    plan = build_trade_plan(
        entry_price=1.04,
        available_capital_usdt=1000,
        price_series=[
            1.0,
            1.02,
            1.04,
        ],
        quote_reserve_usd=10000,
        lp_protected_fraction=None,
        sellability_status="SELLABILITY_OK",
        sellability_data=sellability(),
        exit_evidence={
            **exit_evidence(),
            "observed_min_quote_reserve_usd": 7500.0,
            "reserve_observation_count": 3,
        },
    )

    blockers = set(plan["blockers"])
    unknowns = set(plan["unknowns"])

    assert "LP_PROTECTION_UNKNOWN" not in blockers
    assert "LP_PROTECTION_FRACTION" in unknowns
    assert plan["capital"]["safe_quote_reserve_usd"] == 7500.0
    assert (
        plan["capital"]["liquidity_capacity_source"]
        == "EMPIRICAL_RESERVE_FLOOR"
    )
    assert plan["capital"]["entry_amount_usdt"] > 0



def test_fractional_kelly_is_data_derived_from_tail_risk():
    plan = build_trade_plan(
        entry_price=1.30,
        available_capital_usdt=10000.0,
        price_series=[
            1.00,
            1.20,
            1.10,
            1.30,
        ],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=sellability(),
        exit_evidence=exit_evidence(),
    )

    capital = plan["capital"]
    stats = plan["statistics"]

    assert (
        0
        < capital["kelly_fraction"]
        < capital["full_kelly_fraction"]
        <= 1
    )

    assert (
        0
        < capital["kelly_shrinkage"]
        < 1
    )

    assert (
        stats["observed_downside_rate"]
        == 1 / 3
    )

    es = stats[
        "empirical_expected_shortfall"
    ]

    assert es["state"] == "READY"

    assert (
        stats["tail_risk_fraction"]
        >= es[
            "expected_shortfall_loss_fraction"
        ]
    )


def test_positive_only_series_uses_empirical_stop_risk_without_fake_cvar():
    plan = build_trade_plan(
        entry_price=1.30,
        available_capital_usdt=10000.0,
        price_series=[
            1.00,
            1.10,
            1.20,
            1.30,
        ],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        hard_block=False,
        sellability_data=sellability(),
        exit_evidence=exit_evidence(),
    )

    stats = plan["statistics"]

    assert (
        stats[
            "empirical_expected_shortfall"
        ]["state"]
        == "NO_DOWNSIDE_OBSERVED"
    )

    assert (
        stats["tail_risk_fraction"]
        > 0
    )


def test_dynamic_stop_never_moves_down():
    stop = (
        dynamic_stop_price(
            prices=[
                1.0,
                1.05,
                1.10,
                1.08,
            ],

            highest_price=1.10,

            previous_stop=1.02,
        )
    )

    assert (
        stop >= 1.02
    )


def test_tp1_fraction_is_derived_from_risk_and_price():
    low = (
        tp1_required_fraction(
            token_amount=100,

            remaining_cost_basis_usdt=100,

            current_price=1.5,

            initial_risk_usdt=10,

            realized_pnl_usdt=0,

            cost_model={
                "sell_retention_known": 1.0,

                "sell_gas_usd": 0.0,
            },
        )
    )

    high = (
        tp1_required_fraction(
            token_amount=100,

            remaining_cost_basis_usdt=100,

            current_price=2.0,

            initial_risk_usdt=10,

            realized_pnl_usdt=0,

            cost_model={
                "sell_retention_known": 1.0,

                "sell_gas_usd": 0.0,
            },
        )
    )

    assert (
        0
        < high
        < low
        < 1
    )


def test_single_isolated_move_is_not_entry_evidence():
    from app.strategy.mathematical_trade_plan import (
        build_trade_plan,
        market_statistics,
    )

    prices = [
        4.71300456727626e-05,
        4.71300456727626e-05,
        6.85501785599589e-05,
    ]

    stats = market_statistics(
        prices
    )

    assert (
        stats[
            "informative_return_count"
        ]
        == 1
    )

    plan = build_trade_plan(
        entry_price=prices[-1],
        available_capital_usdt=10000.0,
        price_series=prices,
        quote_reserve_usd=7413.1842,
        lp_protected_fraction=1.0,
        sellability_status=(
            "SELLABILITY_OK"
        ),
        hard_block=False,
        sellability_data={
            "buy_tax": 0.0,
            "sell_tax": 0.0,
        },
        exit_evidence={},
        market_context={
            "runtime_intelligence": {
                "market_quality": {
                    "market_evidence_ready": False,
                    "participation_state": (
                        "CONCENTRATED"
                    ),
                    "liquidity_state": (
                        "STABLE_OR_UNKNOWN"
                    ),
                    "suspicious_volume": True,
                }
            }
        },
    )

    blockers = set(
        plan[
            "blockers"
        ]
    )

    assert (
        plan[
            "paper_eligible"
        ]
        is False
    )

    assert (
        "EMPIRICAL_MOVEMENT_INSUFFICIENT"
        in blockers
    )

    assert (
        "PARTICIPATION_CONCENTRATED"
        in blockers
    )

    assert (
        "SUSPICIOUS_VOLUME"
        in blockers
    )


def test_mature_diverse_evidence_is_not_blocked_by_admission_evidence():
    from app.strategy.mathematical_trade_plan import (
        build_trade_plan,
    )

    plan = build_trade_plan(
        entry_price=1.30,
        available_capital_usdt=10000.0,
        price_series=[
            1.00,
            1.10,
            1.20,
            1.30,
        ],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status=(
            "SELLABILITY_OK"
        ),
        hard_block=False,
        sellability_data={
            "buy_tax": 0.0,
            "sell_tax": 0.0,
        },
        exit_evidence={},
        market_context={
            "runtime_intelligence": {
                "market_quality": {
                    "market_evidence_ready": True,
                    "participation_state": (
                        "DIVERSE"
                    ),
                    "liquidity_state": (
                        "STABLE"
                    ),
                    "suspicious_volume": False,
                }
            }
        },
    )

    blockers = set(
        plan[
            "blockers"
        ]
    )

    assert (
        "EMPIRICAL_MOVEMENT_INSUFFICIENT"
        not in blockers
    )

    assert (
        "PARTICIPATION_EVIDENCE_UNKNOWN"
        not in blockers
    )

    assert (
        "PARTICIPATION_CONCENTRATED"
        not in blockers
    )

    assert (
        "SUSPICIOUS_VOLUME"
        not in blockers
    )



def test_vur_kac_holds_positive_continuation_edge():
    from app.strategy.mathematical_trade_plan import (
        mathematical_vur_kac_state,
    )

    state = mathematical_vur_kac_state(
        prices=[
            1.00,
            1.05,
            1.12,
        ],
        token_amount=100.0,
        remaining_cost_basis_usdt=100.0,
        current_price=1.12,
        cost_model={
            "sell_retention_known": 1.0,
            "sell_gas_usd": 0.0,
        },
        signal_bundle={
            "freshness": "FRESH",
            "coverage": 1.0,
            "flow_momentum": 0.80,
            "flow_acceleration": 0.20,
        },
    )

    assert state["ready"] is True
    assert state["continuation_edge_usdt"] > 0
    assert state["continuation_positive"] is True
    assert state["realize"] is False


def test_vur_kac_realizes_when_price_and_flow_weaken():
    from app.strategy.mathematical_trade_plan import (
        mathematical_vur_kac_state,
    )

    state = mathematical_vur_kac_state(
        prices=[
            1.00,
            1.10,
            1.15,
        ],
        token_amount=100.0,
        remaining_cost_basis_usdt=100.0,
        current_price=1.15,
        cost_model={
            "sell_retention_known": 1.0,
            "sell_gas_usd": 0.0,
        },
        signal_bundle={
            "freshness": "FRESH",
            "coverage": 1.0,
            "flow_momentum": 0.20,
            "flow_acceleration": -0.30,
        },
    )

    assert state["ready"] is True
    assert state["remaining_net_profit_usdt"] > 0
    assert state["price_acceleration"] < 0
    assert state["continuation_edge_usdt"] <= 0
    assert state["realize"] is True
    assert (
        state["reason"]
        == "VUR_KAC_REALIZATION_READY"
    )


def test_vur_kac_missing_flow_stays_unknown():
    from app.strategy.mathematical_trade_plan import (
        mathematical_vur_kac_state,
    )

    state = mathematical_vur_kac_state(
        prices=[
            1.00,
            1.10,
            1.15,
        ],
        token_amount=100.0,
        remaining_cost_basis_usdt=100.0,
        current_price=1.15,
        cost_model={
            "sell_retention_known": 1.0,
            "sell_gas_usd": 0.0,
        },
        signal_bundle={
            "freshness": "FRESH",
            "coverage": 0.5,
            "flow_momentum": 0.20,
            "flow_acceleration": -0.30,
        },
    )

    assert state["ready"] is False
    assert state["realize"] is False
    assert (
        state["reason"]
        == "FLOW_EVIDENCE_NOT_READY"
    )


def test_vur_kac_never_realizes_a_net_losing_position():
    from app.strategy.mathematical_trade_plan import (
        mathematical_vur_kac_state,
    )

    state = mathematical_vur_kac_state(
        prices=[
            1.00,
            1.10,
            1.15,
        ],
        token_amount=100.0,
        remaining_cost_basis_usdt=120.0,
        current_price=1.15,
        cost_model={
            "sell_retention_known": 1.0,
            "sell_gas_usd": 0.0,
        },
        signal_bundle={
            "freshness": "FRESH",
            "coverage": 1.0,
            "flow_momentum": 0.20,
            "flow_acceleration": -0.30,
        },
    )

    assert state["ready"] is True
    assert state["remaining_net_profit_usdt"] < 0
    assert state["realize"] is False
    assert (
        state["reason"]
        == "NO_REALIZABLE_NET_PROFIT"
    )
