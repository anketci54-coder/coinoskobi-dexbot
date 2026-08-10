from app.risk.gate import RiskGate


def test_unknown_sellability_does_not_block():
    result = RiskGate().evaluate({})

    assert result["hard_block"] is False
    assert result["status"] == "PASS"
    assert result["sellability"] == "UNKNOWN"
    assert result["honeypot"] == "UNKNOWN"


def test_confirmed_honeypot_hard_blocks():
    result = RiskGate().evaluate({
        "honeypot": True,
    })

    assert result["hard_block"] is True
    assert result["status"] == "BLOCK"

    assert (
        "HONEYPOT_CONFIRMED"
        in result["hard_block_reasons"]
    )


def test_confirmed_unsellable_hard_blocks():
    result = RiskGate().evaluate({
        "sellable": False,
    })

    assert result["hard_block"] is True

    assert (
        "SELL_NOT_POSSIBLE"
        in result["hard_block_reasons"]
    )


def test_trap_capabilities_are_caution_not_block():
    result = RiskGate().evaluate({
        "mint": True,
        "pause": True,
        "blacklist": True,
        "set_blacklist": True,
        "max_tx": True,
        "max_wallet": True,
    })

    assert result["hard_block"] is False
    assert result["status"] == "CAUTION"

    assert "MINT_CAPABILITY" in (
        result["warning_reasons"]
    )

    assert "PAUSE_CAPABILITY" in (
        result["warning_reasons"]
    )

    assert "BLACKLIST_CAPABILITY" in (
        result["warning_reasons"]
    )


def test_explicit_safe_sellability_passes():
    result = RiskGate().evaluate({
        "honeypot": False,
        "sellable": True,
    })

    assert result["hard_block"] is False
    assert result["status"] == "PASS"
    assert result["honeypot"] == "NO"
    assert result["sellability"] == "SELLABLE"
