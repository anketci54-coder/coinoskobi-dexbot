import pytest

from app.strategy.trailing_stop import (
    ACTION_EXIT_CANDIDATE,
    ACTION_HOLD,
    ProtectiveTrailingStop,
)


def engine():
    return ProtectiveTrailingStop()


def test_initial_stop_is_based_on_highest_price():
    result = engine().evaluate(
        current_price=100.0,
        highest_price=100.0,
        trailing_factor=0.90,
    )

    assert result.highest_price == 100.0
    assert result.stop_price == 90.0
    assert result.action == ACTION_HOLD


def test_new_high_moves_stop_up():
    result = engine().evaluate(
        current_price=150.0,
        highest_price=100.0,
        trailing_factor=0.90,
        previous_stop=90.0,
    )

    assert result.highest_price == 150.0
    assert result.stop_price == 135.0
    assert result.action == ACTION_HOLD


def test_highest_price_never_moves_down():
    result = engine().evaluate(
        current_price=140.0,
        highest_price=150.0,
        trailing_factor=0.90,
        previous_stop=135.0,
    )

    assert result.highest_price == 150.0
    assert result.stop_price == 135.0


def test_stop_never_moves_down():
    result = engine().evaluate(
        current_price=150.0,
        highest_price=150.0,
        trailing_factor=0.80,
        previous_stop=140.0,
    )

    assert result.stop_price == 140.0


def test_price_touching_stop_is_exit_candidate():
    result = engine().evaluate(
        current_price=135.0,
        highest_price=150.0,
        trailing_factor=0.90,
        previous_stop=135.0,
    )

    assert result.action == ACTION_EXIT_CANDIDATE
    assert result.reason == "PROTECTIVE_STOP_REACHED"


def test_price_below_stop_is_exit_candidate():
    result = engine().evaluate(
        current_price=120.0,
        highest_price=150.0,
        trailing_factor=0.90,
        previous_stop=135.0,
    )

    assert result.stop_price == 135.0
    assert result.action == ACTION_EXIT_CANDIDATE


def test_large_upward_gap_tightens_stop():
    result = engine().evaluate(
        current_price=300.0,
        highest_price=100.0,
        trailing_factor=0.90,
        previous_stop=90.0,
    )

    assert result.highest_price == 300.0
    assert result.stop_price == 270.0
    assert result.action == ACTION_HOLD


def test_gap_down_does_not_loosen_stop():
    result = engine().evaluate(
        current_price=200.0,
        highest_price=300.0,
        trailing_factor=0.90,
        previous_stop=270.0,
    )

    assert result.highest_price == 300.0
    assert result.stop_price == 270.0
    assert result.action == ACTION_EXIT_CANDIDATE


def test_authority_is_zero():
    result = engine().evaluate(
        current_price=100.0,
        highest_price=100.0,
        trailing_factor=0.90,
    )

    assert result.decision_authority is False
    assert result.paper_authority is False
    assert result.live_authority is False
    assert result.wallet_authority is False
    assert result.execution_authority is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "current_price": 0,
            "highest_price": 100,
            "trailing_factor": 0.9,
        },
        {
            "current_price": 100,
            "highest_price": 0,
            "trailing_factor": 0.9,
        },
        {
            "current_price": 100,
            "highest_price": 100,
            "trailing_factor": 0,
        },
        {
            "current_price": 100,
            "highest_price": 100,
            "trailing_factor": 1.1,
        },
        {
            "current_price": 100,
            "highest_price": 100,
            "trailing_factor": 0.9,
            "previous_stop": -1,
        },
    ],
)
def test_invalid_inputs_rejected(kwargs):
    with pytest.raises(ValueError):
        engine().evaluate(**kwargs)
