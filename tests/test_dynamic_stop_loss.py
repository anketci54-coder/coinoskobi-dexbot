import pytest

from app.risk.dynamic_stop_loss import (
    calculate_dynamic_sl,
)


def test_missing_measurement_is_unknown():
    r = calculate_dynamic_sl()

    assert r["state"] == "UNKNOWN"
    assert r["sl_distance_pct"] is None


def test_measured_distance_preserved():
    measured = 0.07321

    r = calculate_dynamic_sl(
        measured_sl_distance_pct=measured
    )

    assert r["state"] == "MEASURED"
    assert r["sl_distance_pct"] == pytest.approx(
        measured
    )


def test_measured_prices_derive_distance():
    entry = 100.0
    stop = 92.4

    r = calculate_dynamic_sl(
        entry_price=entry,
        stop_price=stop,
    )

    assert r["sl_distance_pct"] == pytest.approx(
        (entry - stop) / entry
    )


def test_semantics_cannot_invent_stop():
    r = calculate_dynamic_sl(
        flow_momentum=1.0,
        flow_acceleration=1.0,
        liquidity_health="STABLE",
        trend_health="STRONG",
    )

    assert r["state"] == "UNKNOWN"
    assert r["semantic_inputs_used"] is False


def test_authority_zero():
    r = calculate_dynamic_sl(
        measured_sl_distance_pct=0.08123
    )

    assert r["decision_authority"] is False
    assert r["live_authority"] is False
