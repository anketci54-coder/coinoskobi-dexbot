import pytest

from app.strategy.position_lifecycle import (
    PositionLifecycleEngine,
    STATE_OPEN,
    STATE_TP1_DONE,
    STATE_TP2_DONE,
    STATE_TP3_DONE,
    STATE_RUNNER_ACTIVE,
)


def engine():
    return PositionLifecycleEngine()


def test_before_tp1_holds():
    result = engine().evaluate(roi=0.10)

    assert result["state"] == STATE_OPEN
    assert result["action"] == "HOLD"
    assert result["close_fraction"] == 0.0


def test_tp1_closes_20_percent():
    result = engine().evaluate(roi=0.20)

    assert result["state"] == STATE_TP1_DONE
    assert result["action"] == "PARTIAL_CLOSE"
    assert result["close_fraction"] == pytest.approx(0.20)
    assert result["reason"] == "TP1_REACHED"


def test_tp2_closes_25_percent():
    result = engine().evaluate(
        roi=0.50,
        tp1_done=True,
    )

    assert result["state"] == STATE_TP2_DONE
    assert result["action"] == "PARTIAL_CLOSE"
    assert result["close_fraction"] == pytest.approx(0.25)
    assert result["reason"] == "TP2_REACHED"


def test_tp3_closes_25_percent():
    result = engine().evaluate(
        roi=1.00,
        tp1_done=True,
        tp2_done=True,
    )

    assert result["state"] == STATE_TP3_DONE
    assert result["action"] == "PARTIAL_CLOSE"
    assert result["close_fraction"] == pytest.approx(0.25)
    assert result["reason"] == "TP3_REACHED"


def test_runner_after_all_three_targets():
    result = engine().evaluate(
        roi=1.75,
        tp1_done=True,
        tp2_done=True,
        tp3_done=True,
    )

    assert result["state"] == STATE_RUNNER_ACTIVE
    assert result["action"] == "HOLD_RUNNER"
    assert result["close_fraction"] == 0.0


def test_large_jump_advances_only_one_stage():
    result = engine().evaluate(roi=2.00)

    assert result["state"] == STATE_TP1_DONE
    assert result["action"] == "PARTIAL_CLOSE"
    assert result["close_fraction"] == pytest.approx(0.20)


def test_unknown_roi_does_not_close():
    result = engine().evaluate(roi=None)

    assert result["state"] == STATE_OPEN
    assert result["action"] == "HOLD"
    assert result["reason"] == "ROI_UNKNOWN"


def test_contract_has_zero_execution_authority():
    result = engine().evaluate(roi=0.20)

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
