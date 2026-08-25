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


def test_expected_shortfall_accepts_empirical_alpha_zero():
    from app.risk.stream_stats import (
        empirical_expected_shortfall,
    )

    result = empirical_expected_shortfall(
        [-0.10, -0.20, -0.05],
        alpha=0.0,
    )

    assert result["state"] == "READY"
    assert result["tail_count"] == 3
    assert result["expected_shortfall_return"] < 0
    assert (
        result["expected_shortfall_loss_fraction"]
        > 0
    )


def test_ewma_decay_calibration_is_data_derived():
    from app.risk.stream_stats import (
        calibrate_ewma_decay,
    )

    result = calibrate_ewma_decay(
        [
            0.01,
            0.03,
            -0.02,
            0.04,
            -0.01,
        ]
    )

    assert result["state"] == "READY"
    assert 0 < result["decay"] < 1
    assert result["candidate_count"] == 4
    assert result["sample_count"] == 5
    assert result["loss"] >= 0
    assert result["decision_authority"] is False


def test_cusum_calibration_does_not_trigger_its_own_history():
    from app.risk.stream_stats import (
        calibrate_cusum,
        cusum_step,
    )

    values = [
        0.01,
        -0.02,
        0.015,
        -0.04,
        0.01,
    ]

    calibration = calibrate_cusum(
        values
    )

    assert calibration["state"] == "READY"

    up = 0.0
    down = 0.0

    for value in values:
        step = cusum_step(
            value,
            previous_up=up,
            previous_down=down,
            reference=calibration[
                "reference"
            ],
            threshold=calibration[
                "threshold"
            ],
        )

        assert step["change"] == "NO_CHANGE"

        up = step["up_cusum"]
        down = step["down_cusum"]


def test_stream_calibration_refuses_mixed_source_identity():
    from app.risk.stream_stats import (
        calibrate_stream_math,
    )

    rows = [
        {
            "chain": "bsc",
            "dex": "pancakeswap_v2",
            "pool": "0xpool",
            "source": "geckoterminal",
            "price_usd": 1.0,
            "liquidity_usd": 100.0,
        },
        {
            "chain": "bsc",
            "dex": "pancakeswap_v2",
            "pool": "0xpool",
            "source": "dexscreener",
            "price_usd": 1.1,
            "liquidity_usd": 90.0,
        },
    ]

    result = calibrate_stream_math(
        rows
    )

    assert result["state"] == "IDENTITY_MIXED"
    assert result["calibration"] == {}


def test_stream_calibration_requires_real_sequence_depth():
    from app.risk.stream_stats import (
        calibrate_stream_math,
    )

    rows = [
        {
            "chain": "bsc",
            "dex": "pancakeswap_v2",
            "pool": "0xpool",
            "source": "geckoterminal",
            "price_usd": 1.0,
            "liquidity_usd": 100.0,
        },
        {
            "chain": "bsc",
            "dex": "pancakeswap_v2",
            "pool": "0xpool",
            "source": "geckoterminal",
            "price_usd": 1.1,
            "liquidity_usd": 90.0,
        },
    ]

    result = calibrate_stream_math(
        rows
    )

    assert (
        result["state"]
        == "INSUFFICIENT_DATA"
    )

    assert result["calibration"] == {}
