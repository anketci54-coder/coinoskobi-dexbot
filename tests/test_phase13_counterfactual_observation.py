import json
import sqlite3

from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)
from app.paper.schema import ensure_paper_schema


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
    assert result["outcome_scope"] == "PRICE_DIRECTION_ONLY"
    assert result["net_profit_verified"] is False
    assert result["realizable_profit_verified"] is False
    assert result[
        "evaluation_sellability_verified"
    ] is False
    assert result["evaluation_costs_verified"] is False


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
    assert status["automatic_apply_allowed"] is False
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
    assert snapshot[0]["outcome_class"] == "EXPECTED_LOSS"
    assert snapshot[0]["proposal_only"] is True
    assert snapshot[0]["automatic_apply_allowed"] is False
    assert status["outcome_size"] == 1
    assert status["outcome_counts"] == {
        "EXPECTED_LOSS": 1,
    }
    assert status["execution_authority"] is False


def test_durable_counterfactual_horizons_use_paper_db(
    tmp_path,
):
    db_path = tmp_path / "paper.db"

    conn = sqlite3.connect(db_path)
    ensure_paper_schema(conn)
    conn.close()

    store = CounterfactualObservationStore(
        max_entries=8,
        horizon_seconds=300,
        ttl_seconds=900,
        db_path=db_path,
        cache_db_path=None,
    )

    recorded = store.record(
        token="0xdurable",
        pool="0xpool",
        entry_price=1.0,
        signal_state="POSITIVE",
        candidate_action="DOWNGRADE",
        observed_at=1000,
        context={
            "paper": "WATCH",
            "reason": "PLAN_BLOCKED",
            "plan_blockers": [
                "NO_VERIFIED_PERSISTENT_LIQUIDITY",
            ],
            "sizing_blockers": [
                "EXIT_CAPACITY_UNKNOWN",
            ],
        },
    )

    assert recorded["state"] == "RECORDED"
    assert recorded["durable_id"] is not None
    assert recorded["reevaluation_eligible"] is True

    evaluated = store.observe(
        token="0xdurable",
        current_price=1.10,
        evaluated_at=1300,
    )

    assert evaluated["state"] == "EVALUATED"

    store.observe_durable(
        token="0xdurable",
        current_price=1.20,
        evaluated_at=1900,
    )
    store.observe_durable(
        token="0xdurable",
        current_price=0.90,
        evaluated_at=2800,
    )
    store.observe_durable(
        token="0xdurable",
        current_price=1.50,
        evaluated_at=4600,
    )
    store.observe_durable(
        token="0xdurable",
        current_price=2.00,
        evaluated_at=22600,
    )
    store.observe_durable(
        token="0xdurable",
        current_price=3.00,
        evaluated_at=87400,
    )

    rows = store.durable_snapshot(limit=10)
    assert len(rows) == 1

    row = rows[0]

    assert row["price_5m"] == 1.10
    assert row["price_15m"] == 1.20
    assert row["price_30m"] == 0.90
    assert row["price_60m"] == 1.50
    assert row["price_6h"] == 2.00
    assert row["price_24h"] == 3.00

    assert round(row["return_5m"], 6) == 0.10
    assert round(row["return_15m"], 6) == 0.20
    assert round(row["return_30m"], 6) == -0.10
    assert round(row["return_60m"], 6) == 0.50
    assert round(row["return_6h"], 6) == 1.00
    assert round(row["return_24h"], 6) == 2.00

    assert row["max_price"] == 3.00
    assert row["min_price"] == 0.90
    assert round(row["mfe_24h"], 6) == 2.00
    assert round(row["mae_24h"], 6) == -0.10
    assert row["completed_at"] == 87400

    context = json.loads(row["context_json"])

    assert context["reason"] == "PLAN_BLOCKED"
    assert context["plan_blockers"] == [
        "NO_VERIFIED_PERSISTENT_LIQUIDITY",
    ]
    assert context["sizing_blockers"] == [
        "EXIT_CAPACITY_UNKNOWN",
    ]

    status = store.status()

    assert status["ram_only"] is False
    assert status["db_write"] is True
    assert status["durable_tracking"] is True
    assert status["durable_horizons_seconds"] == (
        300,
        900,
        1800,
        3600,
        21600,
        86400,
    )
    assert status["reevaluation_window_seconds"] == 86400
    assert status["permanent_reject"] is False
    assert status["provider_call"] is False
    assert status["decision_authority"] is False
    assert status["paper_authority"] is False
    assert status["live_authority"] is False
    assert status["execution_authority"] is False
