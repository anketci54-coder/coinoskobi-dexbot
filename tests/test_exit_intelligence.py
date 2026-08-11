from app.strategy.exit_intelligence import (
    evaluate_exit_context,
)


def base_signal():
    return {
        "freshness": "FRESH",
        "coverage": 1.0,
        "flow_momentum": 0.4,
        "flow_acceleration": 0.1,
        "reserve_trend": "STABLE",
        "liquidity_health": "STABLE_OR_UNKNOWN",
        "participation_quality": "DIVERSE",
        "wallet_concentration": "DIVERSE",
        "price_impact_health": "HEALTHY",
    }


def test_holding_context():
    result = evaluate_exit_context(
        position_state={
            "tp1_hit": True,
            "tp2_hit": False,
            "tp3_hit": False,
        },
        runner_state={
            "trailing_active": True,
        },
        signal_bundle=base_signal(),
    )

    assert result["state"] == "HOLDING"
    assert result["data_ready"] is True


def test_unknown_when_stale():
    signal = base_signal()
    signal["freshness"] = "STALE"

    result = evaluate_exit_context(
        {},
        {},
        signal,
    )

    assert result["state"] == "UNKNOWN"
    assert result["data_ready"] is False


def test_exit_pressure_on_reserve_break():
    signal = base_signal()
    signal["reserve_trend"] = "BREAK"

    result = evaluate_exit_context(
        {},
        {},
        signal,
    )

    assert result["state"] == "EXIT_PRESSURE"


def test_weakening_flow_and_concentration():
    signal = base_signal()
    signal["flow_momentum"] = -0.2
    signal["flow_acceleration"] = -0.1
    signal["participation_quality"] = "CONCENTRATED"

    result = evaluate_exit_context(
        {},
        {},
        signal,
    )

    assert result["state"] == "WEAKENING"


def test_authority_zero():
    result = evaluate_exit_context(
        {},
        {},
        base_signal(),
    )

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
