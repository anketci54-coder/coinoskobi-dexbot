from app.learning.outcome_memory import OutcomeMemory


def test_false_positive_stored():
    m = OutcomeMemory(10)

    r = m.add(
        "bsc:obs-1",
        "FALSE_POSITIVE",
        chain="bsc",
        signal_family="market_intelligence",
    )

    assert r["state"] == "STORED"
    assert m.count_by_class("FALSE_POSITIVE") == 1


def test_false_negative_stored():
    m = OutcomeMemory(10)

    m.add(
        "bsc:obs-1",
        "FALSE_NEGATIVE",
    )

    assert m.count_by_class("FALSE_NEGATIVE") == 1


def test_avoided_loss_stored():
    m = OutcomeMemory(10)

    m.add(
        "bsc:obs-1",
        "AVOIDED_LOSS",
    )

    assert m.count_by_class("AVOIDED_LOSS") == 1


def test_missed_opportunity_stored():
    m = OutcomeMemory(10)

    m.add(
        "bsc:obs-1",
        "MISSED_OPPORTUNITY",
    )

    assert m.count_by_class("MISSED_OPPORTUNITY") == 1


def test_exit_failure_stored():
    m = OutcomeMemory(10)

    m.add(
        "bsc:obs-1",
        "EXIT_FAILURE",
    )

    assert m.count_by_class("EXIT_FAILURE") == 1


def test_valid_signal_not_memory_error():
    m = OutcomeMemory(10)

    r = m.add(
        "bsc:obs-1",
        "VALID_SIGNAL",
    )

    assert r["state"] == "IGNORED"
    assert m.size == 0


def test_duplicate_not_stored_twice():
    m = OutcomeMemory(10)

    m.add(
        "bsc:obs-1",
        "FALSE_POSITIVE",
    )

    r = m.add(
        "bsc:obs-1",
        "FALSE_POSITIVE",
    )

    assert r["state"] == "DUPLICATE"
    assert m.size == 1


def test_stale_rejected():
    m = OutcomeMemory(10)

    r = m.add(
        "bsc:obs-1",
        "FALSE_POSITIVE",
        freshness="STALE",
    )

    assert r["state"] == "STALE_REJECTED"
    assert m.size == 0


def test_bounded_eviction():
    m = OutcomeMemory(2)

    m.add("a", "FALSE_POSITIVE")
    m.add("b", "FALSE_NEGATIVE")
    m.add("c", "EXIT_FAILURE")

    assert m.size == 2
    assert m.dropped == 1

    ids = [
        row["outcome_id"]
        for row in m.snapshot()
    ]

    assert ids == ["b", "c"]


def test_repeated_error_count():
    m = OutcomeMemory(10)

    m.add(
        "a",
        "FALSE_POSITIVE",
        signal_family="flow_confirmation",
        market_regime="CHOP",
    )
    m.add(
        "b",
        "FALSE_NEGATIVE",
        signal_family="flow_confirmation",
        market_regime="CHOP",
    )
    m.add(
        "c",
        "AVOIDED_LOSS",
        signal_family="flow_confirmation",
        market_regime="CHOP",
    )

    assert m.repeated_error_count(
        signal_family="flow_confirmation",
        market_regime="CHOP",
    ) == 2


def test_single_event_not_persistent_reputation():
    m = OutcomeMemory(10)

    r = m.add(
        "a",
        "FALSE_POSITIVE",
    )

    assert r[
        "persistent_reputation_from_single_event"
    ] is False


def test_authority_zero():
    m = OutcomeMemory(10)

    r = m.add(
        "a",
        "FALSE_NEGATIVE",
    )

    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
