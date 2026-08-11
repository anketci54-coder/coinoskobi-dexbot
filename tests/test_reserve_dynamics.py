from app.dex.reserve_dynamics import (
    analyze_reserve_dynamics,
)


def test_liquidity_shock():
    result = analyze_reserve_dynamics(
        reserve0=60,
        reserve1=65,
        previous_reserve0=100,
        previous_reserve1=100,
    )

    assert result["state"] == "LIQUIDITY_SHOCK"


def test_improving_reserves():
    result = analyze_reserve_dynamics(
        reserve0=120,
        reserve1=115,
        previous_reserve0=100,
        previous_reserve1=100,
    )

    assert result["state"] == "IMPROVING"


def test_unknown_without_history():
    result = analyze_reserve_dynamics(
        reserve0=100,
        reserve1=100,
    )

    assert result["state"] == "UNKNOWN"
