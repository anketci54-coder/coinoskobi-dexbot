from app.strategy.engine import StrategyEngine


def test_missing_token_name_does_not_get_erc20_points():
    result = StrategyEngine().evaluate(
        token={},
        pair={"exists": False, "quote_ok": False},
        risk={},
    )["data"]

    assert result["score"] == 0
    assert "ERC20 OK" not in result["reasons"]


def test_none_token_name_does_not_get_erc20_points():
    result = StrategyEngine().evaluate(
        token={"name": None},
        pair={"exists": False, "quote_ok": False},
        risk={},
    )["data"]

    assert result["score"] == 0
    assert "ERC20 OK" not in result["reasons"]


def test_valid_token_name_gets_erc20_points():
    result = StrategyEngine().evaluate(
        token={"name": "Example Token"},
        pair={"exists": False, "quote_ok": False},
        risk={},
    )["data"]

    assert result["score"] == 5
    assert "ERC20 OK" in result["reasons"]


def test_missing_risk_data_does_not_receive_safe_points():
    result = StrategyEngine().evaluate(
        token={},
        pair={"exists": False, "quote_ok": False},
        risk={},
    )["data"]

    assert result["score"] == 0
    assert "Owner yok" not in result["reasons"]
    assert "Mint yok" not in result["reasons"]
    assert "Pause yok" not in result["reasons"]
    assert "Blacklist yok" not in result["reasons"]
    assert "MaxTx yok" not in result["reasons"]
    assert "MaxWallet yok" not in result["reasons"]


def test_explicit_safe_risk_flags_receive_safe_points():
    risk = {
        "code_size": 0,
        "owner": False,
        "mint": False,
        "pause": False,
        "blacklist": False,
        "max_tx": False,
        "max_wallet": False,
    }

    result = StrategyEngine().evaluate(
        token={},
        pair={"exists": False, "quote_ok": False},
        risk=risk,
    )["data"]

    assert result["score"] == 45


def test_explicit_dangerous_risk_flags_apply_penalties():
    risk = {
        "code_size": 0,
        "owner": True,
        "renounce_owner": False,
        "mint": True,
        "pause": True,
        "blacklist": True,
        "max_tx": True,
        "max_wallet": True,
    }

    result = StrategyEngine().evaluate(
        token={},
        pair={"exists": False, "quote_ok": False},
        risk=risk,
    )["data"]

    assert result["score"] == -55
    assert "Mint var" in result["reasons"]
    assert "Pause var" in result["reasons"]
    assert "Blacklist var" in result["reasons"]
