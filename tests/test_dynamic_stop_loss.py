import pytest

from app.risk.dynamic_stop_loss import calculate_dynamic_sl


def test_neutral_baseline():
    r = calculate_dynamic_sl()

    assert r["sl_distance_pct"] == pytest.approx(0.10)
    assert r["sl_multiplier"] == pytest.approx(0.90)
    assert r["model"] == "DYNAMIC_SL_V1"
    assert r["decision_authority"] is False
    assert r["live_authority"] is False


def test_strong_flow_widens_stop():
    r = calculate_dynamic_sl(
        flow_momentum=1.0,
        flow_acceleration=1.0,
        liquidity_health="STABLE",
        price_impact_health="HEALTHY",
        trend_health="STRONG",
    )

    assert r["sl_distance_pct"] > 0.10
    assert r["sl_multiplier"] == pytest.approx(
        1.0 - r["sl_distance_pct"]
    )


def test_weak_flow_tightens_stop():
    r = calculate_dynamic_sl(
        flow_momentum=-1.0,
        flow_acceleration=-1.0,
        liquidity_health="CRITICAL",
        price_impact_health="CRITICAL",
        trend_health="BREAK",
        exit_pressure="HIGH",
    )

    assert r["sl_distance_pct"] < 0.10


def test_distance_is_clamped_to_risk_envelope():
    high = calculate_dynamic_sl(
        flow_momentum=999,
        flow_acceleration=999,
        liquidity_health="STABLE",
        price_impact_health="HEALTHY",
        trend_health="STRONG",
    )

    low = calculate_dynamic_sl(
        flow_momentum=-999,
        flow_acceleration=-999,
        liquidity_health="CRITICAL",
        price_impact_health="CRITICAL",
        trend_health="BREAK",
        exit_pressure="HIGH",
    )

    assert 0.04 <= high["sl_distance_pct"] <= 0.18
    assert 0.04 <= low["sl_distance_pct"] <= 0.18


def test_invalid_numeric_inputs_are_safe():
    r = calculate_dynamic_sl(
        flow_momentum="bad",
        flow_acceleration=None,
    )

    assert r["sl_distance_pct"] == pytest.approx(0.10)
