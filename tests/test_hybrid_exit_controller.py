import pytest

from app.risk.hybrid_exit_controller import evaluate_hybrid_exit


def test_invalid_price_emergency_exit():
    r = evaluate_hybrid_exit(entry_price=0, current_price=1, highest_price=1, static_sl_price=0.9)
    assert r.action == "EMERGENCY_EXIT"
    assert r.reason == "INVALID_OR_ZERO_PRICE"
    assert r.exit_now is True


def test_hard_block_dominates():
    r = evaluate_hybrid_exit(entry_price=1, current_price=1.2, highest_price=1.2, static_sl_price=0.9, hard_block=True)
    assert r.action == "EMERGENCY_EXIT"
    assert r.reason == "HARD_BLOCK"
    assert r.exit_now is True


@pytest.mark.parametrize("sellability", ["SELLABILITY_FAIL", "SELLABILITY_BLOCK", "UNSELLABLE"])
def test_sellability_block_emergency_exit(sellability):
    r = evaluate_hybrid_exit(entry_price=1, current_price=1.2, highest_price=1.2, static_sl_price=0.9, sellability=sellability)
    assert r.action == "EMERGENCY_EXIT"
    assert r.reason == "SELLABILITY_BLOCK"
    assert r.exit_now is True


def test_persisted_protection_floor_cannot_be_weakened():
    r = evaluate_hybrid_exit(entry_price=1, current_price=0.89, highest_price=1, static_sl_price=0.90)
    assert r.action == "EXIT"
    assert r.reason == "DYNAMIC_PROTECTION_FLOOR"
    assert r.exit_now is True
    assert r.protection_price == pytest.approx(0.90)



def test_advisory_liquidity_cannot_override_math_floor():
    r = evaluate_hybrid_exit(entry_price=1,current_price=1.05,highest_price=1.10,static_sl_price=0.90,liquidity_health=0.10)
    assert r.action == "RUNNER"
    assert r.reason == "MATHEMATICAL_FLOOR_RUNNER"
    assert r.exit_now is False




def test_profitable_position_runs_under_math_floor():
    r = evaluate_hybrid_exit(entry_price=1,current_price=1.20,highest_price=1.20,static_sl_price=0.90,liquidity_health=1.0,flow_momentum=1.0,flow_acceleration=1.0,trend_health=1.0,exit_pressure=0.0,price_impact_health=1.0)
    assert r.action == "RUNNER"
    assert r.protection_price == pytest.approx(0.90)
    assert r.health_score is None




def test_advisory_values_do_not_invent_profit_floor():
    r = evaluate_hybrid_exit(entry_price=1,current_price=1.10,highest_price=1.50,static_sl_price=0.90,liquidity_health=0.50,trend_health=0.50,price_impact_health=0.50)
    assert r.action == "RUNNER"
    assert r.reason == "MATHEMATICAL_FLOOR_RUNNER"
    assert r.protection_price == pytest.approx(0.90)




def test_neutral_position_holds_without_fake_health():
    r = evaluate_hybrid_exit(entry_price=1,current_price=1,highest_price=1,static_sl_price=0.90)
    assert r.action == "HOLD"
    assert r.health_score is None
