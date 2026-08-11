from app.dex.market_regime import classify_market_regime


def test_bull():
    assert classify_market_regime(
        "BULL", "CONFIRMED", "STRENGTHENING", "MULTI_ACTOR"
    )["market_regime"] == "TRENDING_BULL"


def test_bear():
    assert classify_market_regime(
        "BEAR", "CONFIRMED", "STRENGTHENING", "MULTI_ACTOR"
    )["market_regime"] == "TRENDING_BEAR"


def test_conflict():
    assert classify_market_regime(
        "BULL", "CONFLICT", "PRICE_FLOW_DIVERGENCE", "MULTI_ACTOR"
    )["market_regime"] == "CONFLICT"


def test_single_actor_chop():
    assert classify_market_regime(
        "BULL", "CONFIRMED", "STRENGTHENING", "SINGLE_ACTOR_SPIKE"
    )["market_regime"] == "CHOP"


def test_transition():
    assert classify_market_regime(
        "BULL", "PARTIAL_CONFIRMATION", "CONVERGING", "MULTI_ACTOR"
    )["market_regime"] == "TRANSITION"


def test_unknown():
    assert classify_market_regime(
        "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"
    )["market_regime"] == "UNKNOWN"


def test_authority_zero():
    r = classify_market_regime(
        "BULL", "CONFIRMED", "STRENGTHENING", "MULTI_ACTOR"
    )
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
