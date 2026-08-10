from app.risk.traps import (
    TrapRiskAnalyzer,
)


def codes(result):
    return {
        item["code"]
        for item
        in result["signals"]
    }


def test_empty_risk_is_clear():
    result = (
        TrapRiskAnalyzer()
        .evaluate({})
    )

    assert result["status"] == "CLEAR"
    assert result["severity"] == "NONE"
    assert result["signal_count"] == 0
    assert result["hard_block"] is False
    assert result["trade_authority"] is False


def test_unknown_values_do_not_create_risk():
    result = (
        TrapRiskAnalyzer()
        .evaluate({
            "buy_tax": None,
            "sell_tax": None,
            "transfer_tax": None,
        })
    )

    assert result["status"] == "CLEAR"
    assert result["signals"] == []


def test_contract_controls_create_signals():
    result = (
        TrapRiskAnalyzer()
        .evaluate({
            "mint": True,
            "pause": True,
            "blacklist": True,
            "max_tx": True,
        })
    )

    found = codes(result)

    assert "MINT_CAPABILITY" in found
    assert "PAUSE_CAPABILITY" in found
    assert "BLACKLIST_CAPABILITY" in found
    assert "MAX_TX_CONTROL" in found

    assert result["severity"] == "HIGH"

    # Important doctrine:
    # classifier does not hard-block.
    assert result["hard_block"] is False


def test_normal_small_tax_is_low_signal():
    result = (
        TrapRiskAnalyzer()
        .evaluate({
            "buy_tax": 2,
            "sell_tax": 4,
            "transfer_tax": 0,
        })
    )

    found = codes(result)

    assert "BUY_TAX_NONZERO" in found
    assert "SELL_TAX_NONZERO" in found

    assert result["severity"] == "LOW"
    assert result["round_trip_tax"] == 6


def test_elevated_sell_tax_is_medium():
    result = (
        TrapRiskAnalyzer()
        .evaluate({
            "buy_tax": 1,
            "sell_tax": 12,
        })
    )

    assert (
        "SELL_TAX_ELEVATED"
        in codes(result)
    )

    assert result["severity"] == "MEDIUM"


def test_high_round_trip_tax_is_high():
    result = (
        TrapRiskAnalyzer()
        .evaluate({
            "buy_tax": 15,
            "sell_tax": 20,
        })
    )

    assert (
        "ROUND_TRIP_TAX_HIGH"
        in codes(result)
    )

    assert result["round_trip_tax"] == 35
    assert result["severity"] == "HIGH"


def test_extreme_tax_is_critical_signal_not_authority():
    result = (
        TrapRiskAnalyzer()
        .evaluate({
            "sell_tax": 80,
        })
    )

    assert (
        "SELL_TAX_EXTREME"
        in codes(result)
    )

    assert result["severity"] == "CRITICAL"

    # Still no hard block authority here.
    assert result["hard_block"] is False
    assert result["trade_authority"] is False


def test_confirmed_unsellable_is_critical_signal():
    result = (
        TrapRiskAnalyzer()
        .evaluate({
            "sellable": False,
        })
    )

    assert (
        "SELL_NOT_POSSIBLE"
        in codes(result)
    )

    assert result["severity"] == "CRITICAL"

    # Actual blocking remains RiskGate's job.
    assert result["hard_block"] is False
