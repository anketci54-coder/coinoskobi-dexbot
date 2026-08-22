import math

from app.strategy.mathematical_trade_plan import (
    initial_net_risk_usdt,
    realization_values,
    tp1_required_fraction,
    tp2_required_fraction,
)


def close(left, right):
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def test_realization_conserves_inventory():
    result = realization_values(
        token_amount=1000.0,
        fraction=0.25,
        current_price=2.0,
        remaining_cost_basis_usdt=1000.0,
        cost_model={},
    )

    assert result is not None
    assert close(
        result["sold_tokens"],
        250.0,
    )
    assert close(
        result["remaining_tokens"],
        750.0,
    )
    assert close(
        result["sold_tokens"]
        + result["remaining_tokens"],
        1000.0,
    )


def test_realization_conserves_cost_basis():
    result = realization_values(
        token_amount=1000.0,
        fraction=0.25,
        current_price=2.0,
        remaining_cost_basis_usdt=1000.0,
        cost_model={},
    )

    assert result is not None
    assert close(
        result["sold_cost_basis_usdt"],
        250.0,
    )
    assert close(
        result[
            "remaining_cost_basis_usdt"
        ],
        750.0,
    )
    assert close(
        result["sold_cost_basis_usdt"]
        + result[
            "remaining_cost_basis_usdt"
        ],
        1000.0,
    )


def test_realized_pnl_identity():
    result = realization_values(
        token_amount=1000.0,
        fraction=0.25,
        current_price=2.0,
        remaining_cost_basis_usdt=1000.0,
        cost_model={},
    )

    assert result is not None
    assert close(
        result["realized_pnl_usdt"],
        result["net_proceeds_usdt"]
        - result[
            "sold_cost_basis_usdt"
        ],
    )


def test_fraction_above_one_rejected():
    assert (
        realization_values(
            token_amount=100.0,
            fraction=1.000001,
            current_price=2.0,
            remaining_cost_basis_usdt=100.0,
            cost_model={},
        )
        is None
    )


def test_tp1_impossible_target_waits():
    result = tp1_required_fraction(
        token_amount=100.0,
        remaining_cost_basis_usdt=100.0,
        current_price=1.10,
        initial_risk_usdt=20.0,
        realized_pnl_usdt=0.0,
        cost_model={},
    )

    assert result is None


def test_tp1_minimum_reachable_fraction():
    result = tp1_required_fraction(
        token_amount=100.0,
        remaining_cost_basis_usdt=100.0,
        current_price=2.0,
        initial_risk_usdt=20.0,
        realized_pnl_usdt=0.0,
        cost_model={},
    )

    assert result is not None
    assert close(
        result,
        0.20,
    )


def test_tp2_impossible_principal_recovery_waits():
    result = tp2_required_fraction(
        token_amount=100.0,
        current_price=1.0,
        original_entry_usdt=150.0,
        realized_proceeds_usdt=0.0,
        cost_model={},
    )

    assert result is None


def test_tp2_minimum_principal_recovery_fraction():
    result = tp2_required_fraction(
        token_amount=100.0,
        current_price=2.0,
        original_entry_usdt=100.0,
        realized_proceeds_usdt=20.0,
        cost_model={},
    )

    assert result is not None
    assert close(
        result,
        0.40,
    )


def test_initial_net_risk_uses_stop_exit():
    result = initial_net_risk_usdt(
        token_amount=100.0,
        entry_amount_usdt=100.0,
        stop_price=0.80,
        cost_model={},
    )

    assert result is not None
    assert close(
        result,
        20.0,
    )


def test_trade8_bug_shape_cannot_oversell():
    entry_amount = (
        623.8639600815317
    )

    entry_price = (
        5.83522147653643e-05
    )

    current_price = (
        6.05732892241205e-05
    )

    fraction = (
        0.24158004435481112
    )

    tokens = (
        entry_amount
        / entry_price
    )

    result = realization_values(
        token_amount=tokens,
        fraction=fraction,
        current_price=current_price,
        remaining_cost_basis_usdt=entry_amount,
        cost_model={},
    )

    assert result is not None

    expected_sold = (
        tokens
        * fraction
    )

    assert close(
        result["sold_tokens"],
        expected_sold,
    )

    assert (
        result["sold_tokens"]
        <= tokens
    )

    assert close(
        result["gross_proceeds_usdt"],
        expected_sold
        * current_price,
    )

    assert close(
        result["realized_pnl_usdt"],
        5.73662852260432,
    )


def test_trade8_real_initial_risk_not_reachable_at_tp1_price():
    entry_amount = (
        623.8639600815317
    )

    entry_price = (
        5.83522147653643e-05
    )

    stop_price = (
        4.174578273917921e-05
    )

    tp1_observed_price = (
        6.05732892241205e-05
    )

    tokens = (
        entry_amount
        / entry_price
    )

    initial_risk = (
        initial_net_risk_usdt(
            token_amount=tokens,
            entry_amount_usdt=entry_amount,
            stop_price=stop_price,
            cost_model={},
        )
    )

    assert initial_risk is not None
    assert initial_risk > 0

    fraction = tp1_required_fraction(
        token_amount=tokens,
        remaining_cost_basis_usdt=entry_amount,
        current_price=tp1_observed_price,
        initial_risk_usdt=initial_risk,
        realized_pnl_usdt=0.0,
        cost_model={},
    )

    assert fraction is None
