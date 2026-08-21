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
    pos = PositionStateMachine().initial()

    assert pos.state == STATE_OPEN
    assert pos.remaining_fraction == 1.0


def test_measured_tp_sequence():
    sm = PositionStateMachine()
    pos = sm.initial()

    first = 0.173
    second = 0.281

    r1 = sm.apply_tp(
        pos,
        STATE_TP1_DONE,
        close_fraction=first,
    )
    pos = r1["position"]

    r2 = sm.apply_tp(
        pos,
        STATE_TP2_DONE,
        close_fraction=second,
    )
    pos = r2["position"]

    assert r1["close_fraction"] == first
    assert r2["close_fraction"] == second
    assert pos.remaining_fraction == pytest.approx(
        1.0 - first - second
    )


def test_missing_fraction_not_invented():
    sm = PositionStateMachine()

    r = sm.apply_tp(
        sm.initial(),
        STATE_TP1_DONE,
    )

    assert r["applied"] is False
    assert (
        r["reason"]
        == "MEASURED_CLOSE_FRACTION_REQUIRED"
    )


def test_tp3_fixed_target_rejected():
    sm = PositionStateMachine()

    r = sm.apply_tp(
        sm.initial(),
        STATE_TP3_DONE,
        close_fraction=0.2,
    )

    assert r["applied"] is False
    assert (
        r["reason"]
        == "TP3_IS_RUNNER_NOT_FIXED_TARGET"
    )


def test_runner_activation_after_tp2():
    sm = PositionStateMachine()
    pos = sm.initial()

    pos = sm.apply_tp(
        pos,
        STATE_TP1_DONE,
        close_fraction=0.17,
    )["position"]

    pos = sm.apply_tp(
        pos,
        STATE_TP2_DONE,
        close_fraction=0.28,
    )["position"]

    result = sm.activate_runner(pos)

    assert result["applied"] is True
    assert (
        result["position"].state
        == STATE_RUNNER_ACTIVE
    )


def test_duplicate_tp_rejected():
    sm = PositionStateMachine()
    pos = sm.apply_tp(
        sm.initial(),
        STATE_TP1_DONE,
        close_fraction=0.17,
    )["position"]

    r = sm.apply_tp(
        pos,
        STATE_TP1_DONE,
        close_fraction=0.17,
    )

    assert r["applied"] is False


def test_tp_cannot_be_skipped():
    sm = PositionStateMachine()

    r = sm.apply_tp(
        sm.initial(),
        STATE_TP2_DONE,
        close_fraction=0.28,
    )

    assert r["applied"] is False


def test_runner_cannot_activate_early():
    r = PositionStateMachine().activate_runner(
        PositionState()
    )

    assert r["applied"] is False


def test_runner_can_close_remaining():
    sm = PositionStateMachine()
    pos = sm.initial()

    pos = sm.apply_tp(
        pos,
        STATE_TP1_DONE,
        close_fraction=0.17,
    )["position"]

    pos = sm.apply_tp(
        pos,
        STATE_TP2_DONE,
        close_fraction=0.28,
    )["position"]

    pos = sm.activate_runner(
        pos
    )["position"]

    pos = sm.close(
        pos
    )["position"]

    assert pos.state == STATE_CLOSED
    assert pos.remaining_fraction == 0.0
    assert pos.realized_fraction == 1.0


def test_invalid_fraction_conservation_fails():
    sm = PositionStateMachine()

    with pytest.raises(ValueError):
        sm.validate(
            PositionState(
                remaining_fraction=0.5,
                realized_fraction=0.2,
            )
        )


def test_authority_zero():
    authority = (
        PositionStateMachine().authority()
    )

    assert all(
        value is False
        for value in authority.values()
    )
