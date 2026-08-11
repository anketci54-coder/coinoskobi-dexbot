from app.dex.wallet_flow import (
    analyze_wallet_flow,
)


def test_diverse_wallet_flow():
    result = analyze_wallet_flow([
        {"wallet": "a", "notional_usd": 100},
        {"wallet": "b", "notional_usd": 100},
        {"wallet": "c", "notional_usd": 100},
        {"wallet": "d", "notional_usd": 100},
    ])

    assert result["concentration_state"] == "DIVERSE"
    assert result["unique_wallets"] == 4


def test_repeated_wallet_dominance():
    rows = [
        {"wallet": "a", "notional_usd": 100}
        for _ in range(8)
    ]
    rows += [
        {"wallet": "b", "notional_usd": 20}
    ]

    result = analyze_wallet_flow(rows)

    assert (
        result["concentration_state"]
        == "HIGHLY_CONCENTRATED"
    )

    assert result["repeat_ratio"] > 0.70


def test_no_identity_authority():
    result = analyze_wallet_flow([])

    assert result["identity_authority"] is False
    assert result["whale_authority"] is False
