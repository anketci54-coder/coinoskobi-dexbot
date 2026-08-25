import json
import sqlite3
import time

from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)
from app.paper.schema import ensure_paper_schema


def _cache_schema(path):
    db = sqlite3.connect(path)
    db.execute(
        """
        CREATE TABLE gecko_pool_cache(
            pool TEXT PRIMARY KEY,
            token TEXT,
            price_usd REAL,
            updated_at TEXT
        )
        """
    )
    db.commit()
    db.close()


def test_reject_is_timestamped_not_permanent_and_pool_stays_reevaluable(
    tmp_path,
):
    paper_path = tmp_path / "paper.db"
    cache_path = tmp_path / "cache.db"

    db = sqlite3.connect(paper_path)
    ensure_paper_schema(db)
    db.close()
    _cache_schema(cache_path)

    token = "0xabc"
    pool = "0xpool"
    now = time.time()

    cache = sqlite3.connect(cache_path)
    cache.execute(
        """
        INSERT INTO gecko_pool_cache(
            pool, token, price_usd, updated_at
        ) VALUES(?,?,?,datetime('now'))
        """,
        (pool, f"bsc_{token}", 1.0),
    )
    cache.commit()
    cache.close()

    store = CounterfactualObservationStore(
        max_entries=16,
        horizon_seconds=300,
        ttl_seconds=900,
        db_path=paper_path,
        cache_db_path=cache_path,
    )

    first = store.record(
        token=token,
        pool=pool,
        entry_price=1.0,
        signal_state="NEGATIVE",
        candidate_action="BLOCK",
        observed_at=now,
        context={
            "paper": "REJECT",
            "reason": "PLAN_BLOCKED",
            "plan_blockers": [
                "PARTICIPATION_CONCENTRATED",
            ],
            "sizing_blockers": [],
        },
    )

    assert first["state"] == "RECORDED"
    assert first["reevaluation_eligible"] is True
    assert first["reevaluation_window_seconds"] == 86400

    duplicate = store.record(
        token=token,
        pool=pool,
        entry_price=1.01,
        signal_state="NEGATIVE",
        candidate_action="BLOCK",
        observed_at=now + 300,
        context={
            "paper": "REJECT",
            "reason": "PLAN_BLOCKED",
            "plan_blockers": [
                "PARTICIPATION_CONCENTRATED",
            ],
            "sizing_blockers": [],
        },
    )

    decisions = store.decision_snapshot(limit=10)
    assert len(decisions) == 1
    assert duplicate["decision_id"] == first["decision_id"]

    changed = store.record(
        token=token,
        pool=pool,
        entry_price=1.20,
        signal_state="POSITIVE",
        candidate_action="DOWNGRADE",
        observed_at=now + 18 * 3600,
        context={
            "paper": "WATCH",
            "reason": "PLAN_BLOCKED",
            "plan_blockers": [
                "VUR_KAC_ENTRY_NOT_READY",
            ],
            "sizing_blockers": [],
        },
    )

    assert changed["state"] == "RECORDED"
    assert changed["transition_from"] == "REJECT"

    decisions = store.decision_snapshot(limit=10)
    assert len(decisions) == 2
    assert decisions[0]["decision_action"] == "WATCH"
    assert decisions[1]["decision_action"] == "REJECT"

    cache = sqlite3.connect(cache_path)
    cache.execute(
        "DELETE FROM gecko_pool_cache WHERE pool=?",
        (pool,),
    )
    cache.commit()
    preserved = cache.execute(
        "SELECT pool, token FROM gecko_pool_cache WHERE pool=?",
        (pool,),
    ).fetchone()
    cache.close()

    assert preserved == (pool, f"bsc_{token}")

    pending = store.pending_pool_snapshot(max_entries=10)
    assert pending[token] == pool

    status = store.status()
    assert status["permanent_reject"] is False
    assert status["decision_history_timestamped"] is True
    assert status["reevaluation_window_seconds"] == 86400


def test_24h_counterfactual_tracks_mfe_mae_and_promotion(
    tmp_path,
):
    paper_path = tmp_path / "paper.db"
    cache_path = tmp_path / "cache.db"

    db = sqlite3.connect(paper_path)
    ensure_paper_schema(db)
    db.close()
    _cache_schema(cache_path)

    token = "0xdef"
    pool = "0xpool2"
    now = time.time()

    cache = sqlite3.connect(cache_path)
    cache.execute(
        """
        INSERT INTO gecko_pool_cache(
            pool, token, price_usd, updated_at
        ) VALUES(?,?,?,datetime('now'))
        """,
        (pool, f"bsc_{token}", 1.0),
    )
    cache.commit()
    cache.close()

    store = CounterfactualObservationStore(
        max_entries=16,
        horizon_seconds=300,
        ttl_seconds=900,
        db_path=paper_path,
        cache_db_path=cache_path,
    )

    store.record(
        token=token,
        pool=pool,
        entry_price=1.0,
        signal_state="NEGATIVE",
        candidate_action="BLOCK",
        observed_at=now,
        context={
            "paper": "REJECT",
            "reason": "PLAN_BLOCKED",
            "plan_blockers": [
                "VUR_KAC_PRICE_MOMENTUM_NOT_POSITIVE",
            ],
        },
    )

    store.observe_durable(
        token=token,
        current_price=0.40,
        evaluated_at=now + 900,
    )
    store.observe_durable(
        token=token,
        current_price=2.20,
        evaluated_at=now + 21600,
    )

    db = sqlite3.connect(paper_path)
    db.execute(
        """
        INSERT INTO paper_trades(
            created_at,
            token,
            pool,
            entry_price,
            current_price,
            highest_price,
            lowest_price,
            status,
            trade_policy
        ) VALUES(datetime('now'),?,?,?,?,?,?,?,?)
        """,
        (
            token,
            pool,
            2.20,
            2.20,
            2.20,
            2.20,
            "OPEN",
            "VUR_KAC",
        ),
    )
    db.commit()
    db.close()

    store.observe_durable(
        token=token,
        current_price=5.50,
        evaluated_at=now + 18 * 3600,
    )
    store.observe_durable(
        token=token,
        current_price=3.00,
        evaluated_at=now + 86400,
    )

    rows = store.durable_snapshot(limit=10)
    assert len(rows) == 1
    row = rows[0]

    assert round(row["return_6h"], 6) == 1.20
    assert round(row["return_24h"], 6) == 2.00
    assert round(row["mfe_24h"], 6) == 4.50
    assert round(row["mae_24h"], 6) == -0.60
    assert row["first_2x_at"] is not None
    assert row["first_5x_at"] is not None
    assert row["first_50pct_loss_at"] is not None
    assert row["completed_at"] is not None
    assert row["promoted_at"] is not None

    decisions = store.decision_snapshot(limit=10)
    assert decisions[0]["decision_action"] == "PAPER_BUY"
    assert decisions[0]["promotion"] == 1
    assert decisions[1]["decision_action"] == "REJECT"

    promotion_context = json.loads(
        decisions[0]["context_json"]
    )
    assert promotion_context[
        "promotion_from_prior_non_entry"
    ] is True
