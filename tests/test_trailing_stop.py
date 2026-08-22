import pytest

from app.strategy.trailing_stop import (
    ACTION_EXIT_CANDIDATE,
    ACTION_HOLD,
    ProtectiveTrailingStop,
)


def engine():
    return ProtectiveTrailingStop()


def test_measured_stop_is_used():
    r = engine().evaluate(
        current_price=100.0,
        highest_price=100.0,
        measured_stop=92.37,
    )

    assert r.stop_price == pytest.approx(
        92.37
    )
    assert r.action == ACTION_HOLD


def test_new_high_is_recorded():
    r = engine().evaluate(
        current_price=150.0,
        highest_price=100.0,
        measured_stop=127.4,
        previous_stop=92.37,
    )

    assert r.highest_price == 150.0
    assert r.stop_price == pytest.approx(
        127.4
    )


def test_highest_never_moves_down():
    r = engine().evaluate(
        current_price=140.0,
        highest_price=150.0,
        measured_stop=125.0,
        previous_stop=127.4,
    )

    assert r.highest_price == 150.0


def test_stop_never_moves_down():
    r = engine().evaluate(
        current_price=150.0,
        highest_price=150.0,
        measured_stop=120.0,
        previous_stop=140.0,
    )

    assert r.stop_price == 140.0


def test_touching_stop_is_exit_candidate():
    r = engine().evaluate(
        current_price=135.0,
        highest_price=150.0,
        measured_stop=135.0,
    )

    assert r.action == ACTION_EXIT_CANDIDATE


def test_below_stop_is_exit_candidate():
    r = engine().evaluate(
        current_price=120.0,
        highest_price=150.0,
        measured_stop=135.0,
    )

    assert r.action == ACTION_EXIT_CANDIDATE


def test_measured_stop_changes_with_evidence():
    first = engine().evaluate(
        current_price=200.0,
        highest_price=200.0,
        measured_stop=161.0,
    )

    second = engine().evaluate(
        current_price=220.0,
        highest_price=220.0,
        measured_stop=188.0,
        previous_stop=first.stop_price,
    )

    assert second.stop_price == 188.0


def test_gap_down_does_not_loosen_stop():
    r = engine().evaluate(
        current_price=180.0,
        highest_price=220.0,
        measured_stop=160.0,
        previous_stop=188.0,
    )

    assert r.stop_price == 188.0
    assert r.action == ACTION_EXIT_CANDIDATE


def test_authority_zero():
    r = engine().evaluate(
        current_price=100.0,
        highest_price=100.0,
        measured_stop=92.0,
    )

    assert r.decision_authority is False
    assert r.execution_authority is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "current_price": 0,
            "highest_price": 100,
            "measured_stop": 90,
        },
        {
            "current_price": 100,
            "highest_price": 0,
            "measured_stop": 90,
        },
        {
            "current_price": 100,
            "highest_price": 100,
            "measured_stop": 0,
        },
        {
            "current_price": 100,
            "highest_price": 100,
            "measured_stop": 101,
        },
        {
            "current_price": 100,
            "highest_price": 100,
            "measured_stop": 90,
            "previous_stop": -1,
        },
    ],
)
def test_invalid_inputs_rejected(
    kwargs,
):
    with pytest.raises(ValueError):
        engine().evaluate(**kwargs)
