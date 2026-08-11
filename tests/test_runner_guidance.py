from app.strategy.runner_guidance import runner_guidance


def test_continue():
    assert runner_guidance("STRONG")["guidance"] == "CONTINUE"
    assert runner_guidance("HEALTHY")["guidance"] == "CONTINUE"


def test_protect():
    assert runner_guidance("WEAKENING")["guidance"] == "PROTECT"


def test_exit_candidate():
    assert runner_guidance("BREAK")["guidance"] == "EXIT_CANDIDATE"


def test_unknown():
    assert runner_guidance("UNKNOWN")["guidance"] == "UNKNOWN"


def test_authority_zero():
    r = runner_guidance("BREAK")
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
