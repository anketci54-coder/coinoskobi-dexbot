from app.dex.flow_acceleration import (
    analyze_flow_acceleration,
)


def flow(count, volume):
    return {
        "count_imbalance": count,
        "volume_imbalance": volume,
    }


def test_buy_acceleration():
    result = analyze_flow_acceleration(
        short_flow=flow(0.8, 0.9),
        long_flow=flow(0.2, 0.3),
    )

    assert result["state"] == "ACCELERATING_BUY"
    assert result["combined_delta"] > 0


def test_sell_acceleration():
    result = analyze_flow_acceleration(
        short_flow=flow(-0.8, -0.9),
        long_flow=flow(-0.1, -0.2),
    )

    assert result["state"] == "ACCELERATING_SELL"


def test_authority_false():
    result = analyze_flow_acceleration(
        short_flow={},
        long_flow={},
    )

    assert result["live_authority"] is False
    assert result["execution_authority"] is False
