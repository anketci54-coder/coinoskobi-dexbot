import math

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
    assert result["concentration_model"] == "HHI_SHANNON"
    assert result["hhi"] == 0.25
    assert result["normalized_entropy"] == 1.0
    assert result["effective_wallet_count"] == 4.0
    assert result["shannon_entropy"] == math.log(4.0)


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
    assert result["hhi"] > 0.90
    assert result["normalized_entropy"] < 0.20
    assert result["effective_wallet_count"] < 1.10


def test_single_wallet_has_maximum_hhi_and_zero_normalized_entropy():
    result = analyze_wallet_flow([
        {"wallet": "a", "notional_usd": 100},
    ])

    assert result["hhi"] == 1.0
    assert result["shannon_entropy"] == 0.0
    assert result["normalized_entropy"] == 0.0
    assert result["effective_wallet_count"] == 1.0


def test_no_notional_data_keeps_concentration_math_unknown():
    result = analyze_wallet_flow([])

    assert result["hhi"] is None
    assert result["shannon_entropy"] is None
    assert result["normalized_entropy"] is None
    assert result["effective_wallet_count"] is None


def test_non_finite_notional_is_not_allowed_to_poison_math():
    result = analyze_wallet_flow([
        {"wallet": "a", "notional_usd": float("nan")},
        {"wallet": "b", "notional_usd": 100},
    ])

    assert result["total_notional_usd"] == 100.0
    assert result["hhi"] == 1.0
    assert math.isfinite(result["hhi"])


def test_no_identity_authority():
    result = analyze_wallet_flow([])

    assert result["identity_authority"] is False
    assert result["whale_authority"] is False
    assert result["decision_authority"] is False
    assert result["execution_authority"] is False
