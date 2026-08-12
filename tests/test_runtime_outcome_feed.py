from app.learning.runtime_outcome_feed import (
    RuntimeLearningOutcomeFeed,
)


TOKEN = (
    "0x0000000000000000000000000000000000000001"
)


def close(
    feed,
    position_id,
    roi,
    *,
    reason=None,
):
    if reason is None:
        reason = (
            "TAKE_PROFIT"
            if roi > 0
            else "STOP_LOSS"
        )

    return feed.observe_paper_close(
        position_id=position_id,
        token=TOKEN,
        observed_at=(
            "2026-01-01T00:00:00+00:00"
        ),
        evaluated_at=(
            "2026-01-01T00:10:00+00:00"
        ),
        entry_price=1.0,
        exit_price=(
            1.0 + roi
        ),
        realized_return=roi,
        close_reason=reason,
        opening_context=None,
    )


def test_positive_real_paper_close_is_valid_signal():
    feed = RuntimeLearningOutcomeFeed()

    result = close(
        feed,
        1,
        0.20,
    )

    row = result["payload"]

    assert result[
        "state"
    ] == "OBSERVED"

    assert (
        row["classification"][
            "outcome_class"
        ]
        == "VALID_SIGNAL"
    )

    assert row[
        "evidence"
    ][
        "state"
    ] == "EVIDENCE_READY"

    assert (
        row[
            "opening_context_persisted"
        ]
        is False
    )

    # We do not fabricate historical attribution.
    assert row[
        "attribution"
    ][
        "unknown_signals"
    ] == [
        "paper_entry"
    ]


def test_negative_real_paper_close_is_false_positive():
    feed = RuntimeLearningOutcomeFeed()

    result = close(
        feed,
        2,
        -0.10,
    )

    row = result[
        "payload"
    ]

    assert (
        row["classification"][
            "outcome_class"
        ]
        == "FALSE_POSITIVE"
    )

    assert feed.memory.count_by_class(
        "FALSE_POSITIVE"
    ) == 1


def test_duplicate_position_outcome_is_idempotent():
    feed = RuntimeLearningOutcomeFeed()

    first = close(
        feed,
        7,
        0.10,
    )

    second = close(
        feed,
        7,
        0.10,
    )

    assert first[
        "state"
    ] == "OBSERVED"

    assert second[
        "state"
    ] == "DUPLICATE"

    assert feed.event_count == 1

    assert feed.status()[
        "duplicate_count"
    ] == 1


def test_single_trade_cannot_calibrate():
    feed = RuntimeLearningOutcomeFeed(
        min_samples=20
    )

    close(
        feed,
        1,
        0.50,
    )

    result = (
        feed.calibration_snapshot()
    )

    assert result[
        "state"
    ] == "READY"

    payload = result[
        "payload"
    ]

    assert payload[
        "statistics"
    ][
        "state"
    ] == "INSUFFICIENT_SAMPLE"

    assert payload[
        "weight_proposal"
    ][
        "proposal"
    ] == "INSUFFICIENT_EVIDENCE"

    assert payload[
        "weight_proposal"
    ][
        "apply_allowed"
    ] is False


def test_real_sample_count_reaches_calibration():
    feed = RuntimeLearningOutcomeFeed(
        min_samples=20
    )

    for i in range(20):
        close(
            feed,
            i,
            (
                0.10
                if i < 15
                else -0.05
            ),
        )

    payload = (
        feed.calibration_snapshot()
        ["payload"]
    )

    stats = payload[
        "statistics"
    ]

    assert stats[
        "sample_count"
    ] == 20

    assert stats[
        "state"
    ] == "CALIBRATION_READY"

    assert stats[
        "valid_signal_count"
    ] == 15

    assert stats[
        "false_positive_count"
    ] == 5

    assert payload[
        "proposal_only"
    ] is True

    assert payload[
        "automatic_apply_allowed"
    ] is False


def test_feed_is_bounded():
    feed = RuntimeLearningOutcomeFeed(
        max_events=64,
        max_memory=32,
    )

    for i in range(1000):
        close(
            feed,
            i,
            -0.01,
        )

    assert feed.event_count == 64

    assert feed.memory.size == 32

    status = feed.status()

    assert status[
        "bounded"
    ] is True

    assert status[
        "dropped_count"
    ] > 0

    assert status[
        "automatic_apply_allowed"
    ] is False

    assert status[
        "execution_authority"
    ] is False


def test_no_false_negative_or_missed_opportunity_is_invented():
    feed = RuntimeLearningOutcomeFeed()

    for i in range(10):
        close(
            feed,
            i,
            (
                0.1
                if i % 2 == 0
                else -0.1
            ),
        )

    stats = (
        feed.calibration_snapshot()
        ["payload"]
        ["statistics"]
    )

    assert stats[
        "false_negative_count"
    ] == 0

    assert stats[
        "missed_opportunity_count"
    ] == 0
