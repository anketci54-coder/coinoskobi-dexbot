import pytest

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


def test_runner_holds_above_measured_stop():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=0.347,
        current_price=175.0,
        highest_price=175.0,
        measured_stop=157.4,
        previous_stop=150.0,
    )

    assert result.action == RUNNER_HOLD
    assert result.runner_fraction == pytest.approx(
        0.347
    )


def test_runner_stop_uses_new_measurement():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=0.347,
        current_price=200.0,
        highest_price=175.0,
        measured_stop=181.3,
        previous_stop=157.4,
    )

    assert result.highest_price == 200.0
    assert result.stop_price == pytest.approx(
        181.3
    )


def test_runner_stop_never_moves_down():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=0.347,
        current_price=185.0,
        highest_price=200.0,
        measured_stop=170.0,
        previous_stop=181.3,
    )

    assert result.stop_price == pytest.approx(
        181.3
    )


def test_runner_exit_candidate_when_stop_hit():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=0.347,
        current_price=170.0,
        highest_price=200.0,
        measured_stop=181.3,
        previous_stop=181.3,
    )

    assert (
        result.action
        == RUNNER_EXIT_CANDIDATE
    )


def test_runner_has_no_fixed_final_tp():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=0.347,
        current_price=500.0,
        highest_price=500.0,
        measured_stop=410.0,
        previous_stop=300.0,
    )

    assert result.action == RUNNER_HOLD


def test_runner_rejects_wrong_state():
    with pytest.raises(ValueError):
        engine().evaluate(
            position_state=STATE_OPEN,
            remaining_fraction=0.347,
            current_price=100.0,
            highest_price=100.0,
            measured_stop=91.0,
        )


def test_runner_accepts_any_valid_remaining_fraction():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=0.4137,
        current_price=100.0,
        highest_price=100.0,
        measured_stop=91.0,
    )

    assert result.runner_fraction == pytest.approx(
        0.4137
    )


def test_runner_authority_zero():
    result = engine().evaluate(
        position_state=STATE_RUNNER_ACTIVE,
        remaining_fraction=0.347,
        current_price=175.0,
        highest_price=175.0,
        measured_stop=157.4,
    )

    assert result.decision_authority is False
    assert result.execution_authority is False
