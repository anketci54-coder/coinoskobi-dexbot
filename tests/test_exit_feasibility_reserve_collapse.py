from app.risk.reserve_collapse import (
    classify_reserve_collapse,
)


def test_runtime_normal_reserve_move_remains_safe_evidence():
    result = classify_reserve_collapse(
        previous_quote_reserve=17.10235997081519,
        current_quote_reserve=16.729211383923293,
    )

    assert result["state"] == "NO_RESERVE_COLLAPSE"
    assert result["reserve_collapse"] is False
    assert result["catastrophic_reserve_collapse"] is False


def test_runtime_60615_same_pool_drain_is_catastrophic():
    result = classify_reserve_collapse(
        previous_quote_reserve=17.10235997081519,
        current_quote_reserve=0.01576356812299259,
    )

    assert result["reserve_collapse"] is True
    assert result["catastrophic_reserve_collapse"] is True
    assert result["withdrawal_fraction"] > 0.999


def test_runtime_60615_second_sync_is_catastrophic():
    result = classify_reserve_collapse(
        previous_quote_reserve=0.01576356812299259,
        current_quote_reserve=0.000014565959731946,
    )

    assert result["reserve_collapse"] is True
    assert result["catastrophic_reserve_collapse"] is True
    assert result["withdrawal_fraction"] > 0.999
