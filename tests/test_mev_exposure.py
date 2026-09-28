from app.risk.mev import (
    MEVExposureAnalyzer,
    expected_mev_loss,
)


def codes(result):
    return {
        item["code"]
        for item
        in result["signals"]
    }


def test_missing_context_is_unknown_not_risky():
    result = (
        MEVExposureAnalyzer()
        .evaluate({})
    )

    assert result["status"] == "UNKNOWN"
    assert result["severity"] == "NONE"
    assert result["signals"] == []
    assert result["hard_block"] is False
    assert result["trade_authority"] is False


def test_deep_liquidity_small_trade_is_low_exposure():
    result = (
        MEVExposureAnalyzer()
        .evaluate({
            "liquidity_usd": 1_000_000,
            "trade_size_usd": 500,
            "price_impact_pct": 0.1,
            "slippage_pct": 0.2,
        })
    )

    assert result["status"] in (
        "LOW_EXPOSURE",
        "ELEVATED_EXPOSURE",
    )

    assert (
        result["trade_liquidity_pct"]
        == 0.05
    )

    assert result["hard_block"] is False


def test_shallow_liquidity_creates_signal():
    result = (
        MEVExposureAnalyzer()
        .evaluate({
            "liquidity_usd": 8_000,
        })
    )

    assert (
        "SHALLOW_LIQUIDITY_HIGH"
        in codes(result)
    )

    assert result["severity"] == "HIGH"


def test_large_trade_relative_to_pool_is_high():
    result = (
        MEVExposureAnalyzer()
        .evaluate({
            "liquidity_usd": 100_000,
            "trade_size_usd": 2_000,
        })
    )

    assert (
        "TRADE_LIQUIDITY_RATIO_HIGH"
        in codes(result)
    )

    assert (
        result["trade_liquidity_pct"]
        == 2.0
    )


def test_extreme_price_impact_is_critical_signal():
    result = (
        MEVExposureAnalyzer()
        .evaluate({
            "liquidity_usd": 100_000,
            "price_impact_pct": 10,
        })
    )

    assert (
        "PRICE_IMPACT_PCT_CRITICAL"
        in codes(result)
    )

    assert result["severity"] == "CRITICAL"

    # Exposure alone does not create block authority.
    assert result["hard_block"] is False


def test_high_slippage_is_exposure_not_conviction():
    result = (
        MEVExposureAnalyzer()
        .evaluate({
            "slippage_pct": 4,
        })
    )

    assert (
        "SLIPPAGE_PCT_HIGH"
        in codes(result)
    )

    assert result["status"] == "HIGH_EXPOSURE"
    assert result["trade_authority"] is False


def test_negative_values_are_treated_unknown():
    result = (
        MEVExposureAnalyzer()
        .evaluate({
            "liquidity_usd": -1,
            "trade_size_usd": -1,
            "price_impact_pct": -1,
            "slippage_pct": -1,
        })
    )

    assert result["status"] == "UNKNOWN"
    assert result["signals"] == []


def test_expected_mev_loss_requires_real_inputs():
    result = expected_mev_loss(
        None,
        10.0,
    )

    assert result["state"] == "UNKNOWN"
    assert result["expected_mev_loss_usd"] is None
    assert result["decision_authority"] is False


def test_expected_mev_loss_math():
    result = expected_mev_loss(
        0.25,
        12.0,
    )

    assert result["state"] == "READY"
    assert result["expected_mev_loss_usd"] == 3.0
    assert result["trade_authority"] is False


def test_analyzer_exposes_expected_loss_without_changing_authority():
    result = MEVExposureAnalyzer().evaluate({
        "liquidity_usd": 100_000,
        "trade_size_usd": 500,
        "mev_attack_probability": 0.10,
        "mev_conditional_loss_usd": 20.0,
    })

    assert result["expected_loss"]["state"] == "READY"
    assert result["expected_loss"]["expected_mev_loss_usd"] == 2.0
    assert result["hard_block"] is False
    assert result["trade_authority"] is False


def test_mev_loss_envelope_bounds_explicit_minout_headroom():
    from app.risk.mev import mev_loss_envelope

    result = mev_loss_envelope(
        baseline_executable_output_usd=1000.0,
        slippage_tolerance_pct=0.5,
        route_visibility="PUBLIC",
    )

    assert result["state"] == "BOUNDED"
    assert result["loss_upper_bound_usd"] == 5.0
    assert result["decision_reserve_usd"] == 5.0
    assert result["route_visibility"] == "PUBLIC"
    assert result["exposure_class"] == "PUBLIC_OR_UNKNOWN_ROUTE"


def test_protected_route_does_not_zero_mev_bound_without_calibration():
    from app.risk.mev import mev_loss_envelope

    result = mev_loss_envelope(
        baseline_executable_output_usd=1000.0,
        slippage_tolerance_pct=0.5,
        route_visibility="PROTECTED",
    )

    assert result["state"] == "BOUNDED"
    assert result["decision_reserve_usd"] == 5.0
    assert result["exposure_class"] == "PROTECTED_ROUTE"


def test_mev_loss_envelope_is_unbounded_without_explicit_tolerance():
    from app.risk.mev import mev_loss_envelope

    result = mev_loss_envelope(
        baseline_executable_output_usd=1000.0,
        slippage_tolerance_pct=None,
        route_visibility="PUBLIC",
    )

    assert result["state"] == "UNBOUNDED"
    assert result["decision_reserve_usd"] is None
    assert "SLIPPAGE_TOLERANCE_PCT" in result["missing_evidence"]


def test_mev_loss_envelope_uses_executable_output_not_extra_route_components():
    from app.risk.mev import mev_loss_envelope

    # 900 is already the post-route/FOT executable baseline. The envelope only
    # reserves the explicit minOut headroom and does not re-subtract route loss.
    result = mev_loss_envelope(
        baseline_executable_output_usd=900.0,
        slippage_tolerance_pct=1.0,
        route_visibility="UNKNOWN",
    )

    assert result["decision_reserve_usd"] == 9.0
    assert (
        result["double_count_guard"]
        == "BASELINE_ALREADY_INCLUDES_DETERMINISTIC_ROUTE_ECONOMICS"
    )
