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
    opening_context=None,
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
        opening_context=opening_context,
    )


def verified_context(wallet="bsc:0xabc"):
    return {
        "actor_identity": {
            "wallet_id": wallet,
            "actor_id": wallet,
            "identity_source": "TRANSACTION_FROM_ONLY",
            "hindsight_reconstructed": False,
        }
    }


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


def test_verified_entry_wallet_feeds_phase9_realized_percent_once():
    calls = []

    def observer(wallet_id, outcome_id, return_pct, *, realized=False):
        calls.append((wallet_id, outcome_id, return_pct, realized))
        return {
            "state": "OBSERVED",
            "realized_sample_size": 1,
            "decision_authority": False,
            "execution_authority": False,
        }

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=observer
    )

    first = close(
        feed,
        41,
        0.20,
        opening_context=verified_context(),
    )
    duplicate = close(
        feed,
        41,
        0.20,
        opening_context=verified_context(),
    )

    assert calls == [
        (
            "bsc:0xabc",
            "paper-position:41",
            20.0,
            True,
        )
    ]
    assert first["payload"]["phase9_wallet_tracking"]["state"] == "OBSERVED"
    assert first["payload"]["phase9_wallet_tracking"]["source"] == "PAPER_CLOSE_ENTRY_WALLET"
    assert duplicate["state"] == "DUPLICATE"


def test_unverified_or_hindsight_identity_cannot_feed_phase9():
    calls = []

    def observer(*args, **kwargs):
        calls.append((args, kwargs))
        return {"state": "OBSERVED"}

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=observer
    )

    guessed = verified_context()
    guessed["actor_identity"]["identity_source"] = "ROUTER_GUESS"
    hindsight = verified_context()
    hindsight["actor_identity"]["hindsight_reconstructed"] = True

    a = close(feed, 51, 0.10, opening_context=guessed)
    b = close(feed, 52, 0.10, opening_context=hindsight)

    assert calls == []
    assert a["payload"]["phase9_wallet_tracking"]["state"] == "NOT_ELIGIBLE"
    assert b["payload"]["phase9_wallet_tracking"]["state"] == "NOT_ELIGIBLE"


def test_phase9_observer_failure_cannot_break_paper_outcome():
    def observer(*args, **kwargs):
        raise RuntimeError("phase9 unavailable")

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=observer
    )

    result = close(
        feed,
        61,
        0.10,
        opening_context=verified_context(),
    )

    assert result["state"] == "OBSERVED"
    phase9 = result["payload"]["phase9_wallet_tracking"]
    assert phase9["state"] == "DEGRADED"
    assert phase9["reason"] == "RuntimeError"
    assert phase9["execution_authority"] is False


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


def test_degraded_phase9_observer_retries_on_duplicate_replay():
    calls = []

    def observer(wallet_id, outcome_id, return_pct, *, realized=False):
        calls.append((wallet_id, outcome_id, return_pct, realized))
        if len(calls) == 1:
            raise RuntimeError("temporary")
        return {
            "state": "OBSERVED",
            "realized_sample_size": 1,
            "decision_authority": False,
            "execution_authority": False,
        }

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=observer
    )

    first = close(
        feed,
        71,
        0.20,
        opening_context=verified_context(),
    )
    second = close(
        feed,
        71,
        0.20,
        opening_context=verified_context(),
    )

    assert first["state"] == "OBSERVED"
    assert first["payload"]["phase9_wallet_tracking"]["state"] == "OBSERVED"
    assert second["state"] == "DUPLICATE"
    assert second["payload"]["phase9_wallet_tracking"]["state"] == "OBSERVED"
    assert len(calls) == 2
    assert calls[0][1] == calls[1][1] == "paper-position:71"
    assert feed.event_count == 1
    assert feed.accepted_count == 1
    assert feed.duplicate_count == 1


def test_degraded_phase9_retry_queue_survives_multiple_scheduler_passes():
    calls = []

    def observer(wallet_id, outcome_id, return_pct, *, realized=False):
        calls.append((wallet_id, outcome_id, return_pct, realized))
        if len(calls) < 4:
            raise RuntimeError("temporary")
        return {
            "state": "OBSERVED",
            "realized_sample_size": 1,
            "decision_authority": False,
            "execution_authority": False,
        }

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=observer
    )

    first = close(
        feed,
        81,
        0.25,
        opening_context=verified_context(),
    )

    assert first["payload"]["phase9_wallet_tracking"]["state"] == "DEGRADED"
    assert feed.phase9_retry_count == 1

    a = feed.retry_degraded_wallet_outcomes()
    b = feed.retry_degraded_wallet_outcomes()
    c = feed.retry_degraded_wallet_outcomes()

    assert a[0]["phase9_wallet_tracking"]["state"] == "DEGRADED"
    assert b[0]["phase9_wallet_tracking"]["state"] == "DEGRADED"
    assert c[0]["phase9_wallet_tracking"]["state"] == "OBSERVED"
    assert len(calls) == 4
    assert feed.phase9_retry_count == 0
    assert feed.event_snapshot()[0]["phase9_wallet_tracking"]["state"] == "OBSERVED"
    assert feed.accepted_count == 1
    assert feed.duplicate_count == 0


def test_phase9_retry_queue_is_bounded_with_event_store():
    def observer(*args, **kwargs):
        raise RuntimeError("temporary")

    feed = RuntimeLearningOutcomeFeed(
        max_events=2,
        wallet_outcome_observer=observer,
    )

    for position_id in (91, 92, 93):
        close(
            feed,
            position_id,
            0.10,
            opening_context=verified_context(),
        )

    assert feed.event_count == 2
    assert feed.phase9_retry_count == 2
    assert feed.status()["max_phase9_retries"] == 2
