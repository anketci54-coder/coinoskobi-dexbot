from app.strategy.adaptive_trailing import (
    recommend_trailing,
)


def test_requires_measured_stop():
    r = recommend_trailing(
        90.0,
        110.0,
        "RUNNER_HEALTHY",
    )

    assert r["recommended_stop"] == 90.0
    assert (
        r["runner_health"]
        == "MEASURED_STOP_REQUIRED"
    )


def test_measured_stop_tightens():
    r = recommend_trailing(
        90.0,
        110.0,
        measured_stop=96.4,
    )

    assert r["recommended_stop"] == 96.4


def test_measured_stop_never_loosens():
    r = recommend_trailing(
        95.0,
        110.0,
        measured_stop=91.2,
    )

    assert r["recommended_stop"] == 95.0


def test_invalid_measured_stop_keeps_current():
    r = recommend_trailing(
        95.0,
        100.0,
        measured_stop=101.0,
    )

    assert r["recommended_stop"] == 95.0
    assert (
        r["runner_health"]
        == "INVALID_MEASURED_STOP"
    )


def test_invalid_current_state_unknown():
    r = recommend_trailing(
        None,
        100.0,
        measured_stop=96.0,
    )

    assert r["recommended_stop"] is None


def test_authority_zero():
    r = recommend_trailing(
        90.0,
        100.0,
        measured_stop=96.0,
    )

    assert r["modify_stop"] is False
    assert r["execution_authority"] is False
