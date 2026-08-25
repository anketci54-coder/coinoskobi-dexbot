from app.risk.rug_features import (
    build_rug_features,
)


def test_unknown_stays_unknown():
    result = build_rug_features()

    assert result["state"] == "UNKNOWN"
    assert result["rug_probability"] is None
    assert result["calibrated"] is False
    assert result["decision_authority"] is False


def test_known_features_do_not_create_probability():
    result = build_rug_features(
        mint=True,
        blacklist=False,
        lp_protected_fraction=0.80,
        wallet_hhi=0.25,
        wallet_entropy=0.75,
        buy_probability=0.60,
        liquidity_log_change=-0.10,
        pool_age_seconds=120,
    )

    assert result["state"] == "READY"
    assert result["features"]["mint"] is True
    assert result["features"]["lp_protected_fraction"] == 0.80
    assert result["features"]["liquidity_log_change"] == -0.10
    assert result["rug_probability"] is None
    assert result["model_version"] is None
    assert result["trade_authority"] is False


def test_invalid_ratios_become_unknown():
    result = build_rug_features(
        holder_hhi=1.2,
        wallet_hhi=-0.1,
        buy_probability=2.0,
        pool_age_seconds=-1,
    )

    assert result["features"]["holder_hhi"] is None
    assert result["features"]["wallet_hhi"] is None
    assert result["features"]["buy_probability"] is None
    assert result["features"]["pool_age_seconds"] is None
