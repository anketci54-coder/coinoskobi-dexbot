from app.dex.signal_bundle import (
    build_dex_signal_bundle,
)


def full_bundle(age=0.5):
    return build_dex_signal_bundle(
        flow={
            "volume_imbalance": 0.6,
        },
        acceleration={
            "combined_delta": 0.25,
        },
        market_quality={
            "participation_state": "DIVERSE",
            "suspicious_volume": False,
            "liquidity_state": "STABLE_OR_UNKNOWN",
        },
        wallet_flow={
            "concentration_state": "DIVERSE",
        },
        reserve_dynamics={
            "state": "STABLE",
        },
        price_impact={
            "estimated_impact_context": "HEALTHY",
        },
        age_seconds=age,
    )


def test_complete_fresh_bundle():
    result = full_bundle()

    assert result["coverage"] == 1.0
    assert result["coverage_state"] == "COMPLETE"
    assert result["freshness"] == "FRESH"


def test_stale_bundle():
    result = full_bundle(age=10)

    assert result["freshness"] == "STALE"


def test_missing_data_is_partial():
    result = build_dex_signal_bundle(
        flow={},
        market_quality={},
        age_seconds=0.1,
    )

    assert result["coverage"] < 1.0
    assert result["coverage_state"] == "INSUFFICIENT"


def test_bundle_has_no_trade_authority():
    result = full_bundle()

    assert result["trade_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
