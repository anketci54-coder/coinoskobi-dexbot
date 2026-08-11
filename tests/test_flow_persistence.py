from app.dex.flow_persistence import stabilize_confirmation


def test_single_confirm_debounced():
    r = stabilize_confirmation(
        ["UNCONFIRMED"], "CONFIRMED",
        previous="UNCONFIRMED",
    )
    assert r["stable_state"] == "UNCONFIRMED"


def test_confirm_persists():
    r = stabilize_confirmation(
        ["CONFIRMED"], "CONFIRMED",
        previous="UNCONFIRMED",
    )
    assert r["stable_state"] == "CONFIRMED"


def test_single_conflict_debounced():
    r = stabilize_confirmation(
        ["CONFIRMED"], "CONFLICT",
        previous="CONFIRMED",
    )
    assert r["stable_state"] == "CONFIRMED"


def test_conflict_persists():
    r = stabilize_confirmation(
        ["CONFLICT"], "CONFLICT",
        previous="CONFIRMED",
    )
    assert r["stable_state"] == "CONFLICT"


def test_partial_immediate():
    r = stabilize_confirmation(
        ["CONFIRMED"], "PARTIAL_CONFIRMATION",
        previous="CONFIRMED",
    )
    assert r["stable_state"] == "PARTIAL_CONFIRMATION"


def test_authority_zero():
    r = stabilize_confirmation([], "UNKNOWN")
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
