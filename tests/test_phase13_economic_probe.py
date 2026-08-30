from app.learning.economic_probe import economic_capacity_probe_1usdt


def test_probe_limits_price_only_exit_above_pool_liquidity():
    result = economic_capacity_probe_1usdt(
        entry_price=0.00001,
        horizon_price=100.0,
        liquidity_usd=20_000.0,
    )

    assert result["state"] == "LIMITED"
    assert result["price_only_exit_usdt"] == 10_000_000.0
    assert result["liquidity_usd"] == 20_000.0


def test_probe_does_not_claim_verified_without_reserve_route_evidence():
    result = economic_capacity_probe_1usdt(
        entry_price=1.0,
        horizon_price=10.0,
        liquidity_usd=20_000.0,
    )

    assert result["state"] == "UNKNOWN"
    assert result["reason"] == "EXACT_RESERVE_ROUTE_EVIDENCE_REQUIRED"
    assert result["price_only_exit_usdt"] == 10.0


def test_probe_missing_liquidity_is_unknown():
    result = economic_capacity_probe_1usdt(
        entry_price=1.0,
        horizon_price=1000.0,
        liquidity_usd=None,
    )

    assert result["state"] == "UNKNOWN"
    assert result["reason"] == "PROBE_EVIDENCE_MISSING"
