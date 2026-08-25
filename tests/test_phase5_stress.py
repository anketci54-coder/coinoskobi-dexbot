from app.dex.wallet_flow import analyze_wallet_flow
from app.dex.reserve_dynamics import analyze_reserve_dynamics
from app.dex.price_impact import analyze_price_impact


def test_fake_volume_concentrated_wallets_do_not_look_clean():
    wallet = analyze_wallet_flow([
        {"wallet": "bot", "notional_usd": 1000}
        for _ in range(20)
    ])

    assert (
        wallet["concentration_state"]
        == "HIGHLY_CONCENTRATED"
    )


def test_liquidity_withdrawal_is_visible():
    reserves = analyze_reserve_dynamics(
        reserve0=40,
        reserve1=45,
        previous_reserve0=100,
        previous_reserve1=100,
    )

    assert reserves["state"] == "LIQUIDITY_SHOCK"


def test_shallow_market_large_trade_visible():
    result = analyze_price_impact(
        trade_size_usd=5000,
        liquidity_usd=20_000,
    )

    assert result[
        "estimated_impact_context"
    ] == "CRITICAL"
