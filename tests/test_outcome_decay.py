from app.learning.outcome_decay import (
    classify_window,
    decay_outcome_weight,
    build_evidence_window_summary,
)


def test_recent_window():
    assert classify_window(0) == "RECENT"
    assert classify_window(49) == "RECENT"


def test_medium_window():
    assert classify_window(50) == "MEDIUM"
    assert classify_window(199) == "MEDIUM"


def test_long_window():
    assert classify_window(200) == "LONG"
    assert classify_window(999) == "LONG"


def test_archival_window():
    assert classify_window(1000) == "ARCHIVAL"


def test_recent_soft_not_decayed():
    r = decay_outcome_weight(
        10,
        hard_evidence=False,
    )

    assert r[
        "effective_weight"
    ] == 1.0

    assert r[
        "decay_applied"
    ] is False


def test_medium_soft_decays():
    r = decay_outcome_weight(
        100,
        hard_evidence=False,
    )

    assert r[
        "effective_weight"
    ] == 0.7


def test_long_soft_decays_more():
    r = decay_outcome_weight(
        500,
        hard_evidence=False,
    )

    assert r[
        "effective_weight"
    ] == 0.4


def test_archival_soft_has_low_weight():
    r = decay_outcome_weight(
        5000,
        hard_evidence=False,
    )

    assert r[
        "effective_weight"
    ] == 0.15


def test_hard_evidence_never_decays():
    for age in (
        10,
        100,
        500,
        5000,
    ):
        r = decay_outcome_weight(
            age,
            hard_evidence=True,
        )

        assert r[
            "effective_weight"
        ] == 1.0

        assert r[
            "decay_applied"
        ] is False

        assert r[
            "hard_evidence_preserved"
        ] is True


def test_regime_change_reduces_soft_weight():
    same = decay_outcome_weight(
        100,
        hard_evidence=False,
        same_regime=True,
    )

    changed = decay_outcome_weight(
        100,
        hard_evidence=False,
        same_regime=False,
    )

    assert (
        changed["effective_weight"]
        < same["effective_weight"]
    )


def test_regime_change_does_not_reduce_hard_evidence():
    r = decay_outcome_weight(
        5000,
        hard_evidence=True,
        same_regime=False,
    )

    assert r[
        "effective_weight"
    ] == 1.0


def test_decay_never_deletes_history():
    r = decay_outcome_weight(
        5000,
        hard_evidence=False,
    )

    assert r[
        "record_deleted"
    ] is False

    assert r[
        "historical_record_preserved"
    ] is True


def test_summary_counts_windows():
    r = build_evidence_window_summary([
        {
            "age": 10,
        },
        {
            "age": 100,
        },
        {
            "age": 500,
        },
        {
            "age": 5000,
        },
    ])

    assert r[
        "window_counts"
    ] == {
        "RECENT": 1,
        "MEDIUM": 1,
        "LONG": 1,
        "ARCHIVAL": 1,
    }


def test_summary_preserves_hard_soft_split():
    r = build_evidence_window_summary([
        {
            "age": 5000,
            "hard_evidence": True,
        },
        {
            "age": 5000,
            "hard_evidence": False,
        },
    ])

    assert r[
        "hard_evidence_count"
    ] == 1

    assert r[
        "soft_evidence_count"
    ] == 1

    assert r[
        "hard_evidence_preserved"
    ] is True


def test_authority_and_apply_zero():
    r = decay_outcome_weight(
        100
    )

    assert (
        r["automatic_apply_allowed"]
        is False
    )

    assert (
        r["decision_authority"]
        is False
    )

    assert (
        r["paper_authority"]
        is False
    )

    assert (
        r["live_authority"]
        is False
    )

    assert (
        r["wallet_authority"]
        is False
    )

    assert (
        r["execution_authority"]
        is False
    )
