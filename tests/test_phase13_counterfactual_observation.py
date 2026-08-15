from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)


def _store():
    return CounterfactualObservationStore(
        max_entries=2,
        horizon_seconds=300,
        ttl_seconds=900,
    )


def test_negative_block_down_is_avoided_loss():
    store = _store()

    assert store.record(
        token="0xa",
        pool="0xpool",
        entry_price=1.0,
        signal_state="NEGATIVE",
        candidate_action="BLOCK",
        observed_at=1000,
    )["state"] == "RECORDED"

    result = store.observe(
        token="0xa",
        current_price=0.5,
        evaluated_at=1300,
    )

    assert result["state"] == "EVALUATED"
    assert result["outcome_class"] == "AVOIDED_LOSS"
    assert result["realized_return"] == -0.5


def test_negative_block_up_is_false_negative():
    store = _store()

    store.record(
        token="0xa",
        pool="0xpool",
        entry_price=1.0,
        signal_state="NEGATIVE",
        candidate_action="BLOCK",
        observed_at=1000,
    )

    result = store.observe(
        token="0xa",
        current_price=1.5,
        evaluated_at=1300,
    )

    assert result["outcome_class"] == "FALSE_NEGATIVE"


def test_positive_downgrade_up_is_missed_opportunity():
    store = _store()

    store.record(
        token="0xa",
        pool="0xpool",
        entry_price=1.0,
        signal_state="POSITIVE",
        candidate_action="DOWNGRADE",
        observed_at=1000,
    )

    result = store.observe(
        token="0xa",
        current_price=1.2,
        evaluated_at=1300,
    )

    assert result["outcome_class"] == "MISSED_OPPORTUNITY"


def test_store_is_pending_bounded_and_authority_free():
    store = _store()

    for token in ("0xa", "0xb", "0xc"):
        store.record(
            token=token,
            pool="0xpool",
            entry_price=1.0,
            signal_state="POSITIVE",
            candidate_action="DOWNGRADE",
            observed_at=1000,
        )

    assert store.size == 2
    assert store.evicted_count == 1

    result = store.observe(
        token="0xc",
        current_price=1.1,
        evaluated_at=1100,
    )

    assert result["state"] == "PENDING"

    status = store.status()

    assert status["bounded"] is True
    assert status["ram_only"] is True
    assert status["db_write"] is False
    assert status["provider_call"] is False
    assert status[
        "automatic_apply_allowed"
    ] is False
    assert status["execution_authority"] is False



def test_evaluated_outcomes_are_bounded_in_memory():
    store = _store()

    store.record(
        token="0xa",
        pool="0xpool",
        entry_price=1.0,
        signal_state="POSITIVE",
        candidate_action="DOWNGRADE",
        observed_at=1000,
        context={
            "score": 92,
            "sellability": "SELLABILITY_UNKNOWN",
        },
    )

    store.observe(
        token="0xa",
        current_price=0.8,
        evaluated_at=1300,
    )

    snapshot = store.outcome_snapshot()
    status = store.status()

    assert len(snapshot) == 1
    assert snapshot[0]["outcome_class"] == (
        "EXPECTED_LOSS"
    )
    assert snapshot[0]["proposal_only"] is True
    assert snapshot[0][
        "automatic_apply_allowed"
    ] is False
    assert status["outcome_size"] == 1
    assert status["outcome_counts"] == {
        "EXPECTED_LOSS": 1,
    }
    assert status["execution_authority"] is False
