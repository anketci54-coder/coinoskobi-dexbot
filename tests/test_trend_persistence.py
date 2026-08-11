from app.strategy.trend_persistence import stabilize_trend


def test_single_break_debounced():
    r = stabilize_trend(
        ["HEALTHY"],
        "BREAK",
        previous="HEALTHY",
    )
    assert r["confirmed_state"] == "HEALTHY"


def test_second_break_confirms():
    r = stabilize_trend(
        ["HEALTHY", "BREAK"],
        "BREAK",
        previous="HEALTHY",
    )
    assert r["confirmed_state"] == "BREAK"


def test_single_weakening_debounced():
    r = stabilize_trend(
        ["STRONG"],
        "WEAKENING",
        previous="STRONG",
    )
    assert r["confirmed_state"] == "STRONG"


def test_healthy_immediate():
    r = stabilize_trend(
        ["BREAK"],
        "HEALTHY",
        previous="BREAK",
    )
    assert r["confirmed_state"] == "HEALTHY"


def test_authority_zero():
    r = stabilize_trend([], "STRONG")
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
