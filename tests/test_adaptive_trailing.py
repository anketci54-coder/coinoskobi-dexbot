from app.strategy.adaptive_trailing import recommend_trailing


def test_healthy():
    r = recommend_trailing(90, 110, "RUNNER_HEALTHY")
    assert r["recommended_stop"] == 99


def test_tighten():
    r = recommend_trailing(90, 100, "RUNNER_TIGHTEN")
    assert r["recommended_stop"] == 97


def test_stop_never_moves_down():
    r = recommend_trailing(98, 100, "RUNNER_PROTECT")
    assert r["recommended_stop"] == 98


def test_exit_candidate_tight():
    r = recommend_trailing(90, 100, "RUNNER_EXIT_CANDIDATE")
    assert r["recommended_stop"] == 99


def test_unknown_keeps_stop():
    r = recommend_trailing(95, 100, "UNKNOWN")
    assert r["recommended_stop"] == 95


def test_authority_zero():
    r = recommend_trailing(90, 100, "RUNNER_TIGHTEN")
    assert r["modify_stop"] is False
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
