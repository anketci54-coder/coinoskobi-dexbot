import sqlite3

from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)
from app.learning.horizon_integrity import (
    IntegrityCounterfactualObservationStore,
)
from app.paper.schema import ensure_paper_schema


def _store(tmp_path):
    paper = tmp_path / "paper.db"
    cache = tmp_path / "cache.db"

    db = sqlite3.connect(paper)
    ensure_paper_schema(db)
    db.close()

    db = sqlite3.connect(cache)
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

    return CounterfactualObservationStore(
        db_path=paper,
        cache_db_path=cache,
    )


def _insert_pending(
    store,
    *,
    token,
    pool,
    observed_at,
    price=1.0,
):
    store._db.execute(
        """
        INSERT INTO counterfactual_observations(
            token,
            pool,
            observed_at,
            entry_price,
            signal_state,
            candidate_action,
            context_json,
            last_observed_at,
            last_price,
            max_price,
            min_price
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            token,
            pool,
            observed_at,
            price,
            "POSITIVE",
            "DOWNGRADE",
            "{}",
            observed_at,
            price,
            price,
            price,
        ),
    )
    store._db.commit()


def test_public_store_uses_integrity_hardening():
    assert CounterfactualObservationStore is (
        IntegrityCounterfactualObservationStore
    )


def test_pending_scheduler_prioritizes_overdue_not_newest(tmp_path):
    store = _store(tmp_path)
    now = 2_000_000.0

    for index in range(121):
        _insert_pending(
            store,
            token=f"0xfresh{index:04d}",
            pool=f"0xpool{index:04d}",
            observed_at=now - 10,
        )

    old_token = "0xold"
    old_pool = "0xoldpool"
    _insert_pending(
        store,
        token=old_token,
        pool=old_pool,
        observed_at=now - 25 * 3600,
    )

    pending = store.pending_pool_snapshot(
        max_entries=120,
        now=now,
    )

    assert len(pending) == 120
    assert pending[old_token] == old_pool


def test_multi_pool_token_gets_exact_handles_and_no_cross_write(tmp_path):
    store = _store(tmp_path)
    now = 3_000_000.0
    token = "0xsame"
    pool_a = "0xpoola"
    pool_b = "0xpoolb"

    _insert_pending(
        store,
        token=token,
        pool=pool_a,
        observed_at=now - 1000,
    )
    _insert_pending(
        store,
        token=token,
        pool=pool_b,
        observed_at=now - 1000,
    )

    pending = store.pending_pool_snapshot(
        max_entries=10,
        now=now,
    )

    assert len(pending) == 2
    handles = {
        pool: handle
        for handle, pool in pending.items()
    }
    assert "::pool::" in handles[pool_a]
    assert "::pool::" in handles[pool_b]

    result = store.observe_durable(
        token=handles[pool_a],
        current_price=2.0,
        evaluated_at=now,
    )

    assert result["state"] == "OBSERVED"
    assert result["exact_pool"] == pool_a

    rows = store._db.execute(
        """
        SELECT pool, price_5m, price_15m
        FROM counterfactual_observations
        WHERE token=?
        ORDER BY pool
        """,
        (token,),
    ).fetchall()
    rows = {
        row["pool"]: row
        for row in rows
    }

    assert rows[pool_a]["price_5m"] == 2.0
    assert rows[pool_a]["price_15m"] == 2.0
    assert rows[pool_b]["price_5m"] is None
    assert rows[pool_b]["price_15m"] is None


def test_ambiguous_raw_token_fails_closed(tmp_path):
    store = _store(tmp_path)
    now = 4_000_000.0
    token = "0xambiguous"

    _insert_pending(
        store,
        token=token,
        pool="0xpool1",
        observed_at=now - 1000,
    )
    _insert_pending(
        store,
        token=token,
        pool="0xpool2",
        observed_at=now - 1000,
    )

    result = store.observe_durable(
        token=token,
        current_price=3.0,
        evaluated_at=now,
    )

    assert result["state"] == "AMBIGUOUS_POOL"
    assert result["durable_updated"] == 0

    changed = store._db.execute(
        """
        SELECT COUNT(*)
        FROM counterfactual_observations
        WHERE token=?
          AND price_5m IS NOT NULL
        """,
        (token,),
    ).fetchone()[0]
    assert changed == 0


def test_legacy_completed_without_24h_is_quarantined(tmp_path):
    store = _store(tmp_path)
    now = 5_000_000.0

    _insert_pending(
        store,
        token="0xlegacy",
        pool="0xlegacypool",
        observed_at=now - 90000,
    )
    store._db.execute(
        """
        UPDATE counterfactual_observations
        SET completed_at=?
        WHERE token='0xlegacy'
        """,
        (now - 1000,),
    )
    store._db.commit()

    quality = store.training_quality_snapshot()

    assert quality["legacy_completed_without_24h"] == 1
    assert quality["legacy_training_disposition"] == "QUARANTINE"
    assert quality["scheduler_policy"] == (
        "CHECKPOINT_DUE_OVERDUE_FIRST"
    )
    assert quality["identity_policy"] == "EXACT_TOKEN_POOL"
    assert quality["training_authority"] is False
    assert quality["live_authority"] is False
