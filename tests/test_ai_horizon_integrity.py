import sqlite3

from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)
from app.learning.horizon_quality import (
    ScientificCounterfactualObservationStore,
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


def test_public_store_uses_scientific_integrity_hardening():
    assert CounterfactualObservationStore is (
        ScientificCounterfactualObservationStore
    )


def test_pending_scheduler_classifies_expired_before_fetch(tmp_path):
    store = _store(tmp_path)
    now = 2_000_000.0

    expired_token = "0xexpired"
    expired_pool = "0xexpiredpool"
    _insert_pending(
        store,
        token=expired_token,
        pool=expired_pool,
        observed_at=now - 25 * 3600,
    )

    fresh_token = "0xfresh"
    fresh_pool = "0xfreshpool"
    _insert_pending(
        store,
        token=fresh_token,
        pool=fresh_pool,
        observed_at=now - 420,
    )

    pending = store.pending_pool_snapshot(
        max_entries=120,
        now=now,
    )

    assert fresh_token in pending
    assert pending[fresh_token] == fresh_pool
    assert expired_token not in pending

    expired = store._db.execute(
        """
        SELECT quality_5m, quality_24h, completed_at
        FROM counterfactual_observations
        WHERE token=? AND pool=?
        """,
        (expired_token, expired_pool),
    ).fetchone()

    assert expired["quality_5m"] == "INTERNAL_GAP"
    assert expired["quality_24h"] == "INTERNAL_GAP"
    assert expired["completed_at"] == now


def test_pending_scheduler_preserves_capture_window_candidate(tmp_path):
    store = _store(tmp_path)
    now = 2_500_000.0

    for index in range(121):
        _insert_pending(
            store,
            token=f"0xfuture{index:04d}",
            pool=f"0xpool{index:04d}",
            observed_at=now - 10,
        )

    target_token = "0xdue"
    target_pool = "0xduepool"
    _insert_pending(
        store,
        token=target_token,
        pool=target_pool,
        observed_at=now - 420,
    )

    pending = store.pending_pool_snapshot(
        max_entries=120,
        now=now,
    )

    assert len(pending) == 120
    assert pending[target_token] == target_pool


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
        SELECT
            pool,
            price_5m,
            quality_5m,
            price_15m,
            quality_15m
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

    assert rows[pool_a]["price_5m"] is None
    assert rows[pool_a]["quality_5m"] == "INTERNAL_GAP"
    assert rows[pool_a]["price_15m"] == 2.0
    assert rows[pool_a]["quality_15m"] == "VALID"
    assert rows[pool_b]["price_5m"] is None
    assert rows[pool_b]["quality_5m"] is None
    assert rows[pool_b]["price_15m"] is None
    assert rows[pool_b]["quality_15m"] is None


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


def test_paper_promotion_is_bound_to_exact_pool(tmp_path):
    store = _store(tmp_path)
    now = 4_500_000.0
    token = "0xmulti"
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

    store._db.execute(
        """
        INSERT INTO paper_trades(
            token,
            pool,
            entry_price,
            status
        ) VALUES(?,?,?,?)
        """,
        (token, pool_b, 1.25, "OPEN"),
    )
    store._db.commit()

    result = store.observe_durable(
        token=token,
        pool=pool_a,
        current_price=2.0,
        evaluated_at=now,
    )

    assert result["state"] == "OBSERVED"
    assert result["promotion"] is None

    result = store.observe_durable(
        token=token,
        pool=pool_b,
        current_price=2.0,
        evaluated_at=now + 1,
    )

    assert result["state"] == "OBSERVED"
    assert result["promotion"] is not None


def test_followup_registry_retains_pool_past_24h_checkpoint(tmp_path):
    store = _store(tmp_path)
    observed_at = 5_000_000.0
    token = "0xretain"
    pool = "0xretainpool"

    assert store._register_followup(
        token=token,
        pool=pool,
        observed_at=observed_at,
    ) is True

    db = sqlite3.connect(store._cache_db_path)
    expires_at = db.execute(
        """
        SELECT expires_at
        FROM candidate_followup_registry
        WHERE pool=?
        """,
        (pool,),
    ).fetchone()[0]
    db.close()

    assert expires_at == observed_at + 86400 + 3600


def test_on_time_horizon_is_valid_and_records_delay(tmp_path):
    store = _store(tmp_path)
    now = 5_250_000.0
    token = "0xvalid"
    pool = "0xvalidpool"

    _insert_pending(
        store,
        token=token,
        pool=pool,
        observed_at=now - 420,
    )

    result = store.observe_durable(
        token=token,
        pool=pool,
        current_price=1.5,
        evaluated_at=now,
    )

    assert result["state"] == "OBSERVED"
    row = store._db.execute(
        """
        SELECT price_5m, quality_5m, delay_5m
        FROM counterfactual_observations
        WHERE token=? AND pool=?
        """,
        (token, pool),
    ).fetchone()

    assert row["price_5m"] == 1.5
    assert row["quality_5m"] == "VALID"
    assert row["delay_5m"] == 120.0


def test_stale_24h_checkpoint_is_gap_not_fabricated_price(tmp_path):
    store = _store(tmp_path)
    now = 5_400_000.0
    token = "0xstale"
    pool = "0xstalepool"

    _insert_pending(
        store,
        token=token,
        pool=pool,
        observed_at=now - 90000,
    )

    pending = store.pending_pool_snapshot(
        max_entries=10,
        now=now,
    )
    assert token not in pending

    row = store._db.execute(
        """
        SELECT
            price_24h,
            return_24h,
            observed_24h_at,
            quality_24h,
            delay_24h,
            completed_at
        FROM counterfactual_observations
        WHERE token=? AND pool=?
        """,
        (token, pool),
    ).fetchone()

    assert row["price_24h"] is None
    assert row["return_24h"] is None
    assert row["observed_24h_at"] is None
    assert row["quality_24h"] == "INTERNAL_GAP"
    assert row["delay_24h"] == 3600.0
    assert row["completed_at"] == now

    quality = store.training_quality_snapshot()
    assert quality["internal_gap_counts"]["24h"] == 1
    assert quality["expired_horizon_policy"] == (
        "LOCAL_GAP_BEFORE_PROVIDER_FETCH"
    )
    assert quality["stale_backfill_allowed"] is False


def test_legacy_completed_without_24h_is_quarantined(tmp_path):
    store = _store(tmp_path)
    now = 5_500_000.0

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
    assert quality["promotion_identity_policy"] == "EXACT_TOKEN_POOL"
    assert quality["followup_retention_grace_seconds"] == 3600
    assert quality["scientific_label_policy"] == (
        "CAPTURE_WINDOW_OR_EXPLICIT_GAP"
    )
    assert quality["horizon_capture_window_seconds"] == 300
    assert quality["training_authority"] is False
    assert quality["live_authority"] is False
