import pytest

from app.strategy.position_lifecycle import (
    PositionLifecycleEngine,
    STATE_OPEN,
    STATE_TP1_DONE,
    STATE_TP2_DONE,
    STATE_RUNNER_ACTIVE,
)


def engine():
    return PositionLifecycleEngine()


def plan():
    return {
        "eligible": True,
        "tp1_roi": 0.137,
        "tp2_roi": 0.412,
        "tp1_close_fraction": 0.271,
        "tp2_close_fraction": 0.319,
    }


def test_before_tp1_holds():
    result = engine().evaluate(
        roi=0.10,
        plan=plan(),
    )

    assert result["state"] == STATE_OPEN
    assert result["action"] == "HOLD"


def test_tp1_uses_plan_fraction():
    result = engine().evaluate(
        roi=0.14,
        plan=plan(),
    )

    assert result["state"] == STATE_TP1_DONE
    assert result["close_fraction"] == pytest.approx(
        plan()["tp1_close_fraction"]
    )


def test_tp2_uses_plan_fraction():
    result = engine().evaluate(
        roi=0.42,
        plan=plan(),
        tp1_done=True,
    )

    assert result["state"] == STATE_TP2_DONE
    assert result["close_fraction"] == pytest.approx(
        plan()["tp2_close_fraction"]
    )


def test_after_tp2_is_runner():
    result = engine().evaluate(
        roi=0.60,
        plan=plan(),
        tp1_done=True,
        tp2_done=True,
    )

    assert result["state"] == STATE_RUNNER_ACTIVE
    assert result["action"] == "HOLD_RUNNER"


def test_large_jump_advances_one_stage():
    result = engine().evaluate(
        roi=2.0,
        plan=plan(),
    )

    assert result["state"] == STATE_TP1_DONE


def test_unknown_roi_holds():
    result = engine().evaluate(
        roi=None,
        plan=plan(),
    )

    assert result["reason"] == "ROI_UNKNOWN"


def test_missing_plan_does_not_invent_targets():
    result = engine().evaluate(
        roi=2.0,
        plan={},
    )

    assert (
        result["reason"]
        == "MATHEMATICAL_PLAN_REQUIRED"
    )


def test_authority_zero():
    result = engine().evaluate(
        roi=0.14,
        plan=plan(),
    )

    assert result["decision_authority"] is False
    assert result["execution_authority"] is False
