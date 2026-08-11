from app.dex.flow_divergence import evaluate_divergence


def test_bull_strengthening():
    assert evaluate_divergence(
        "UP", 40, 10
    )["divergence_state"] == "STRENGTHENING"


def test_bull_converging():
    assert evaluate_divergence(
        "UP", 40, -5
    )["divergence_state"] == "CONVERGING"


def test_bull_divergence():
    assert evaluate_divergence(
        "UP", -20, -5
    )["divergence_state"] == "PRICE_FLOW_DIVERGENCE"


def test_bear_strengthening():
    assert evaluate_divergence(
        "DOWN", -40, -10
    )["divergence_state"] == "STRENGTHENING"


def test_bear_converging():
    assert evaluate_divergence(
        "DOWN", -40, 5
    )["divergence_state"] == "CONVERGING"


def test_unknown():
    assert evaluate_divergence(
        None, None, None
    )["divergence_state"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_divergence("UP", 10, 1)
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
