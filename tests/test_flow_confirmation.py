from app.dex.flow_confirmation import confirm_flow


def test_confirmed_bull():
    assert confirm_flow(
        "BULL", 40, 10, "DIVERSE"
    )["confirmation"] == "CONFIRMED"


def test_confirmed_bear():
    assert confirm_flow(
        "BEAR", -40, -10, "DIVERSE"
    )["confirmation"] == "CONFIRMED"


def test_partial():
    assert confirm_flow(
        "BULL", 30, -2, "DIVERSE"
    )["confirmation"] == "PARTIAL_CONFIRMATION"


def test_conflict():
    assert confirm_flow(
        "BULL", -20, -5, "DIVERSE"
    )["confirmation"] == "CONFLICT"


def test_unconfirmed():
    assert confirm_flow(
        "BULL", 0, 0, "DIVERSE"
    )["confirmation"] == "UNCONFIRMED"


def test_unknown():
    assert confirm_flow(
        None, None, None, None
    )["confirmation"] == "UNKNOWN"


def test_authority_zero():
    r = confirm_flow("BULL", 10, 1, "DIVERSE")
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
