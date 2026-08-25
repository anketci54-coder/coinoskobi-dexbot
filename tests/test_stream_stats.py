import math

from app.risk.stream_stats import (
    cusum_step,
    empirical_expected_shortfall,
    ewma_variance_step,
    log_change,
)


def test_log_change():
    assert log_change(110, 100) == math.log(1.1)


def test_log_change_requires_positive_prices():
    assert log_change(0, 100) is None
    assert log_change(100, 0) is None


def test_ewma_requires_calibrated_decay():
    result = ewma_variance_step(0.01)

    assert result["state"] == "UNCALIBRATED"
    assert result["ewma_variance"] is None
    assert result["decision_authority"] is False


def test_ewma_one_step():
    result = ewma_variance_step(
        0.02,
        previous_variance=0.0001,
        decay=0.9,
    )

    expected = 0.9 * 0.0001 + 0.1 * 0.0004

    assert abs(result["ewma_variance"] - expected) < 1e-12
    assert abs(
        result["ewma_volatility"]
        - math.sqrt(expected)
    ) < 1e-12


def test_cusum_requires_calibration():
    result = cusum_step(-0.1)

    assert result["state"] == "UNCALIBRATED"
    assert result["change"] == "UNKNOWN"


def test_cusum_detects_down_change():
    result = cusum_step(
        -0.20,
        previous_down=0.10,
        reference=0.01,
        threshold=0.20,
    )

    assert result["state"] == "READY"
    assert result["down_cusum"] >= 0.20
    assert result["change"] == "DOWN_CHANGE"
    assert result["decision_authority"] is False


def test_expected_shortfall_requires_explicit_alpha():
    result = empirical_expected_shortfall(
        [-0.10, 0.01, 0.02],
    )

    assert result["state"] == "UNCALIBRATED"
    assert result["expected_shortfall_return"] is None


def test_expected_shortfall_uses_observed_worst_tail():
    returns = [
        -0.20,
        -0.10,
        -0.05,
        0.00,
        0.01,
        0.02,
        0.03,
        0.04,
        0.05,
        0.06,
    ]

    result = empirical_expected_shortfall(
        returns,
        alpha=0.80,
    )

    assert result["state"] == "READY"
    assert result["tail_count"] == 2
    assert result["var_return"] == -0.10
    assert abs(
        result["expected_shortfall_return"]
        - (-0.15)
    ) < 1e-12
    assert (
        result["expected_shortfall_loss_fraction"]
        > 0
    )
    assert result["decision_authority"] is False
