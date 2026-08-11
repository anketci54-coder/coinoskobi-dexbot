from app.strategy.runner_exit_binding import bind_runner_exit


def test_continue():
    r = bind_runner_exit(
        {"runner_active": True},
        {"guidance": "CONTINUE"},
    )
    assert r["recommendation"] == "KEEP_RUNNING"


def test_protect():
    r = bind_runner_exit(
        {"runner_active": True},
        {"guidance": "PROTECT"},
    )
    assert r["recommendation"] == "TIGHTEN_PROTECTION"


def test_exit_candidate():
    r = bind_runner_exit(
        {"runner_active": True},
        {"guidance": "EXIT_CANDIDATE"},
    )
    assert r["recommendation"] == "PREPARE_EXIT"


def test_no_runner():
    r = bind_runner_exit(
        {"runner_active": False},
        {"guidance": "EXIT_CANDIDATE"},
    )
    assert r["recommendation"] == "NO_RUNNER"


def test_no_execution_authority():
    r = bind_runner_exit(
        {"runner_active": True},
        {"guidance": "EXIT_CANDIDATE"},
    )
    assert r["modify_stop"] is False
    assert r["execute_exit"] is False
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
