import pytest

from app.risk.reserve_collapse import (
    classify_reserve_collapse,
)


def test_normal_reserve_move_is_not_collapse():
    result = classify_reserve_collapse(
        previous_quote_reserve=17.10,
        current_quote_reserve=16.70,
    )

    assert result["state"] == "NO_RESERVE_COLLAPSE"
    assert result["reserve_collapse"] is False
    assert result["catastrophic_reserve_collapse"] is False


def test_60615_real_pool_event_is_catastrophic_collapse():
    result = classify_reserve_collapse(
        previous_quote_reserve=17.10235997081519,
        current_quote_reserve=0.000014565959731946,
    )

    assert (
        result["state"]
        == "CATASTROPHIC_RESERVE_COLLAPSE"
    )
    assert result["reserve_collapse"] is True
    assert result["catastrophic_reserve_collapse"] is True
    assert result["withdrawal_fraction"] > 0.99999
    assert result["remaining_fraction"] == pytest.approx(
        0.000014565959731946 / 17.10235997081519
    )


def test_60615_followup_reserve_remains_catastrophically_depleted():
    result = classify_reserve_collapse(
        previous_quote_reserve=17.10235997081519,
        current_quote_reserve=0.000076565959731946,
    )

    assert result["catastrophic_reserve_collapse"] is True
    assert result["withdrawal_fraction"] > 0.99999


def test_unknown_evidence_stays_unknown():
    result = classify_reserve_collapse(
        previous_quote_reserve=None,
        current_quote_reserve=1.0,
    )

    assert result["state"] == "UNKNOWN"
    assert result["reserve_collapse"] is False
    assert result["withdrawal_fraction"] is None
