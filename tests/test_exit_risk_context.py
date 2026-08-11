from app.strategy.exit_risk_context import evaluate_exit_risk


def test_clean():
    r = evaluate_exit_risk(True, "STABLE", "LOW", True)
    assert r["hard_risk"] is False


def test_sellability():
    r = evaluate_exit_risk(False, "STABLE", "LOW", True)
    assert "SELLABILITY_FAIL" in r["reasons"]


def test_liquidity():
    r = evaluate_exit_risk(True, "COLLAPSE", "LOW", True)
    assert "LIQUIDITY_HARD_RISK" in r["reasons"]


def test_mev():
    r = evaluate_exit_risk(True, "STABLE", "HIGH", True)
    assert "MEV_HIGH_RISK" in r["reasons"]


def test_execution():
    r = evaluate_exit_risk(True, "STABLE", "LOW", False)
    assert "EXECUTION_NOT_FEASIBLE" in r["reasons"]


def test_authority_zero():
    r = evaluate_exit_risk(False, "COLLAPSE", "HIGH", False)
    assert r["trend_override"] is True
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
