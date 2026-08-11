import pytest

from app.config.trading import RUNNER_FRACTION
from app.strategy.position_state import (
    STATE_OPEN,
    STATE_RUNNER_ACTIVE,
)
from app.strategy.runner import (
    RUNNER_EXIT_CANDIDATE,
    RUNNER_HOLD,
    RunnerEngine,
)


def engine():
    return RunnerEngine()


def test_runner_holds_above_stop():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=RUNNER_FRACTION,
        current_price=175,
        highest_price=175,
        trailing_factor=0.90,
        previous_stop=150,
    )

    assert result.action == RUNNER_HOLD
    assert result.runner_fraction == pytest.approx(
        RUNNER_FRACTION
    )
    assert result.stop_price == pytest.approx(157.5)


def test_runner_stop_moves_up_with_new_high():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=RUNNER_FRACTION,
        current_price=200,
        highest_price=175,
        trailing_factor=0.90,
        previous_stop=157.5,
    )

    assert result.action == RUNNER_HOLD
    assert result.highest_price == 200
    assert result.stop_price == pytest.approx(180)


def test_runner_stop_never_moves_down():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=RUNNER_FRACTION,
        current_price=185,
        highest_price=200,
        trailing_factor=0.80,
        previous_stop=180,
    )

    assert result.stop_price == 180


def test_runner_exit_candidate_when_stop_hit():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=RUNNER_FRACTION,
        current_price=170,
        highest_price=200,
        trailing_factor=0.90,
        previous_stop=180,
    )

    assert result.action == RUNNER_EXIT_CANDIDATE
    assert result.reason == (
        "RUNNER_PROTECTIVE_STOP_REACHED"
    )


def test_runner_has_no_fixed_final_tp():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=RUNNER_FRACTION,
        current_price=500,
        highest_price=500,
        trailing_factor=0.90,
        previous_stop=300,
    )

    assert result.action == RUNNER_HOLD
    assert result.stop_price == pytest.approx(450)


def test_runner_rejects_wrong_state():
    with pytest.raises(ValueError):
        engine().evaluate(
            position_state=STATE_OPEN,
            remaining_fraction=RUNNER_FRACTION,
            current_price=100,
            highest_price=100,
            trailing_factor=0.90,
        )


def test_runner_rejects_wrong_fraction():
    with pytest.raises(ValueError):
        engine().evaluate(
            position_state=STATE_RUNNER_ACTIVE,
            remaining_fraction=0.40,
            current_price=100,
            highest_price=100,
            trailing_factor=0.90,
        )


def test_runner_authority_is_zero():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=RUNNER_FRACTION,
        current_price=175,
        highest_price=175,
        trailing_factor=0.90,
    )

    assert result.decision_authority is False
    assert result.paper_authority is False
    assert result.live_authority is False
    assert result.wallet_authority is False
    assert result.execution_authority is False
