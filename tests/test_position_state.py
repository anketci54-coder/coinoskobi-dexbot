import pytest

from app.strategy.position_state import (
    PositionState,
    PositionStateMachine,
    STATE_OPEN,
    STATE_TP1_DONE,
    STATE_TP2_DONE,
    STATE_TP3_DONE,
    STATE_RUNNER_ACTIVE,
    STATE_CLOSED,
)


def test_initial_state():
    sm = PositionStateMachine()
    pos = sm.initial()

    assert pos.state == STATE_OPEN
    assert pos.remaining_fraction == 1.0
    assert pos.realized_fraction == 0.0


def test_full_tp_sequence_leaves_30_percent_runner():
    sm = PositionStateMachine()
    pos = sm.initial()

    r1 = sm.apply_tp(pos, STATE_TP1_DONE)
    pos = r1["position"]

    assert r1["close_fraction"] == 0.20
    assert pos.remaining_fraction == 0.80

    r2 = sm.apply_tp(pos, STATE_TP2_DONE)
    pos = r2["position"]

    assert r2["close_fraction"] == 0.25
    assert pos.remaining_fraction == 0.55

    r3 = sm.apply_tp(pos, STATE_TP3_DONE)
    pos = r3["position"]

    assert r3["close_fraction"] == 0.25
    assert pos.remaining_fraction == 0.30
    assert pos.realized_fraction == 0.70
    assert pos.runner_fraction == 0.30


def test_runner_activation():
    sm = PositionStateMachine()
    pos = sm.initial()

    pos = sm.apply_tp(
        pos, STATE_TP1_DONE
    )["position"]

    pos = sm.apply_tp(
        pos, STATE_TP2_DONE
    )["position"]

    pos = sm.apply_tp(
        pos, STATE_TP3_DONE
    )["position"]

    result = sm.activate_runner(pos)
    pos = result["position"]

    assert result["applied"] is True
    assert pos.state == STATE_RUNNER_ACTIVE
    assert pos.remaining_fraction == 0.30


def test_duplicate_tp_is_rejected():
    sm = PositionStateMachine()
    pos = sm.initial()

    pos = sm.apply_tp(
        pos, STATE_TP1_DONE
    )["position"]

    result = sm.apply_tp(
        pos, STATE_TP1_DONE
    )

    assert result["applied"] is False
    assert result["position"] == pos


def test_tp_cannot_be_skipped():
    sm = PositionStateMachine()
    pos = sm.initial()

    result = sm.apply_tp(
        pos, STATE_TP2_DONE
    )

    assert result["applied"] is False
    assert result["position"].state == STATE_OPEN


def test_runner_cannot_activate_early():
    sm = PositionStateMachine()
    pos = sm.initial()

    result = sm.activate_runner(pos)

    assert result["applied"] is False
    assert result["reason"] == "RUNNER_NOT_READY"


def test_runner_can_close_remaining_position():
    sm = PositionStateMachine()
    pos = sm.initial()

    for state in (
        STATE_TP1_DONE,
        STATE_TP2_DONE,
        STATE_TP3_DONE,
    ):
        pos = sm.apply_tp(
            pos, state
        )["position"]

    pos = sm.activate_runner(
        pos
    )["position"]

    result = sm.close(pos)
    pos = result["position"]

    assert pos.state == STATE_CLOSED
    assert pos.remaining_fraction == 0.0
    assert pos.realized_fraction == 1.0


def test_closed_position_cannot_close_twice():
    sm = PositionStateMachine()
    pos = sm.close(sm.initial())["position"]

    result = sm.close(pos)

    assert result["applied"] is False
    assert result["reason"] == "ALREADY_CLOSED"


def test_invalid_fraction_conservation_fails():
    sm = PositionStateMachine()

    pos = PositionState(
        remaining_fraction=0.50,
        realized_fraction=0.20,
    )

    with pytest.raises(ValueError):
        sm.validate(pos)


def test_invalid_tp_flag_order_fails():
    sm = PositionStateMachine()

    pos = PositionState(
        tp2_done=True,
    )

    with pytest.raises(ValueError):
        sm.validate(pos)


def test_authority_is_zero():
    authority = PositionStateMachine().authority()

    assert all(
        value is False
        for value in authority.values()
    )
