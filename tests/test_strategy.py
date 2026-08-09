from app.strategy.engine import StrategyEngine


def test_missing_token_name_does_not_get_erc20_points():
    result = StrategyEngine().evaluate(
        token={},
        pair={"exists": False, "quote_ok": False},
        risk={},
    )["data"]

    assert result["score"] == 45
    assert "ERC20 OK" not in result["reasons"]


def test_none_token_name_does_not_get_erc20_points():
    result = StrategyEngine().evaluate(
        token={"name": None},
        pair={"exists": False, "quote_ok": False},
        risk={},
    )["data"]

    assert result["score"] == 45
    assert "ERC20 OK" not in result["reasons"]


def test_valid_token_name_gets_erc20_points():
    result = StrategyEngine().evaluate(
        token={"name": "Example Token"},
        pair={"exists": False, "quote_ok": False},
        risk={},
    )["data"]

    assert result["score"] == 50
    assert "ERC20 OK" in result["reasons"]
