import math

from app.risk.paper_position_sizing import (
    calculate_paper_position_size,
)


def _plan(
    *,
    raw_amount,
    available,
    reserve,
    risk_distance,
    known_edge,
    full_edge=None,
    cost_complete=False,
):
    return {
        "capital": {
            "entry_amount_usdt": raw_amount,
            "available_usdt": available,
            "safe_quote_reserve_usd": reserve,
            "kelly_fraction": 1.0,
        },
        "expected": {
            "known_net_edge_fraction": (
                known_edge
            ),
            "full_net_edge_fraction": (
                full_edge
            ),
        },
        "cost_model": {
            "cost_complete": (
                cost_complete
            ),
        },
        "market_statistics": {
            "risk_log_distance": (
                risk_distance
            ),
        },
    }


def test_edge_cannot_expand_exit_capacity(
    tmp_path,
):
    # Empty outcome DB => safely blocked.
    plan = _plan(
        raw_amount=9000,
        available=10000,
        reserve=2000,
        risk_distance=0.4,
        known_edge=9.0,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(
            tmp_path / "missing.db"
        ),
    )

    assert (
        result["entry_amount_usdt"]
        == 0.0
    )

    assert (
        "GAP_RISK_UNOBSERVED"
        in result["blockers"]
    )


def test_current_db_calibration_is_data_derived():
    plan = _plan(
        raw_amount=9000,
        available=10000,
        reserve=2000,
        risk_distance=0.4,
        known_edge=9.0,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    if result["gap_multiplier"] is None:
        assert (
            result["entry_amount_usdt"]
            == 0.0
        )
        return

    expected_cap = (
        2000
        * math.exp(-0.4)
        / result["gap_multiplier"]
    )

    assert (
        result["entry_amount_usdt"]
        <= expected_cap + 1e-9
    )

    assert (
        result["entry_amount_usdt"]
        <= 2000
    )

    assert (
        result["kelly_diagnostic_only"]
        is True
    )


def test_incomplete_cost_does_not_equal_zero():
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.25,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    assert (
        result[
            "empirical_cost_uncertainty_fraction"
        ]
        is not None
        or result["entry_amount_usdt"] == 0.0
    )


def test_full_net_edge_used_when_complete():
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=99.0,
        full_edge=0.15,
        cost_complete=True,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    if result["entry_amount_usdt"] > 0:
        assert (
            result["effective_edge_fraction"]
            == 0.15
        )


def test_negative_effective_edge_blocks():
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=-0.01,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    assert (
        result["entry_amount_usdt"]
        == 0.0
    )
