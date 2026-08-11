from app.strategy.runner_health import evaluate_runner_health


def test_healthy():
    assert evaluate_runner_health(
        "STRONG", "NONE", "NONE"
    )["runner_health"] == "RUNNER_HEALTHY"


def test_protect():
    assert evaluate_runner_health(
        "WEAKENING", "EARLY", "BUILDING"
    )["runner_health"] == "RUNNER_PROTECT"


def test_tighten():
    assert evaluate_runner_health(
        "HEALTHY", "CONFIRMED", "HIGH"
    )["runner_health"] == "RUNNER_TIGHTEN"


def test_exit_candidate():
    assert evaluate_runner_health(
        "BREAK", "EARLY", "BUILDING"
    )["runner_health"] == "RUNNER_EXIT_CANDIDATE"


def test_emergency_context():
    assert evaluate_runner_health(
        "BREAK", "CONFIRMED", "HIGH"
    )["runner_health"] == "RUNNER_EMERGENCY_EXIT_CONTEXT"


def test_unknown():
    assert evaluate_runner_health(
        "UNKNOWN", "NONE", "NONE"
    )["runner_health"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_runner_health("BREAK", "CONFIRMED", "HIGH")
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
