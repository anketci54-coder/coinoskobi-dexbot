"""Learning package bootstrap.

The durable counterfactual store is hardened at package import so existing
runtime imports keep the same public class contract while gaining checkpoint-
first scheduling, exact token+pool identity, scientific horizon-label quality
and a conservative one-USDT economic-capacity label.
"""

import sqlite3
import threading
from pathlib import Path

from app.paper.database import DB as _PAPER_DB

from . import counterfactual_observation as _counterfactual_observation
from . import horizon_quality as _horizon_quality
from . import watch_probe_store as _watch_probe_store
from . import watch_probe_entry_snapshot as _watch_probe_entry_snapshot
from .economic_probe import EconomicProbeCounterfactualObservationStore


# Preserve the established public scientific-store identity while layering the
# Phase 13 economic probe underneath the same runtime-facing class contract.
_horizon_quality.ScientificCounterfactualObservationStore = (
    EconomicProbeCounterfactualObservationStore
)
_counterfactual_observation.CounterfactualObservationStore = (
    EconomicProbeCounterfactualObservationStore
)

ScientificCounterfactualObservationStore = (
    EconomicProbeCounterfactualObservationStore
)


# Candidate analysis is concurrent and PipelineEngine intentionally creates the
# WATCH stores lazily. For the configured production paper DB, two workers may
# therefore both pass the engine's ``is None`` check before either publishes its
# store. Constructor-only locking is insufficient: it can still leave two live
# store instances with independent runtime locks.
#
# Make each configured WATCH store a process singleton and initialize that
# single object while holding one shared lock. Every racing constructor call
# therefore returns the same fully initialized object. Test/non-production DB
# paths retain normal independent-instance semantics.
_watch_store_init_lock = threading.RLock()
_OriginalWatchProbeStore = _watch_probe_store.WatchProbeStore
_OriginalWatchProbeEntrySnapshotStore = (
    _watch_probe_entry_snapshot.WatchProbeEntrySnapshotStore
)


def _resolved_db_key(db_path):
    try:
        return Path(db_path).resolve(strict=False).as_posix()
    except (TypeError, ValueError, OSError):
        return None


_CONFIGURED_PAPER_DB_KEY = _resolved_db_key(_PAPER_DB)


def _canonical_paper_db_key(db_path):
    resolved = _resolved_db_key(db_path)
    if (
        resolved is None
        or _CONFIGURED_PAPER_DB_KEY is None
        or resolved != _CONFIGURED_PAPER_DB_KEY
    ):
        return None
    return resolved


def _schema_columns(db, table):
    try:
        return {
            str(row[1])
            for row in db.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }
    except sqlite3.Error:
        return set()


def _schema_object_exists(db, object_type, name):
    try:
        return (
            db.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type=? AND name=?
                LIMIT 1
                """,
                (object_type, name),
            ).fetchone()
            is not None
        )
    except sqlite3.Error:
        return False


_WATCH_PROBE_COLUMNS = {
    "id",
    "token",
    "pool",
    "opened_at",
    "entry_price",
    "entry_usdt",
    "token_amount",
    "last_observed_at",
    "last_price",
    "max_price",
    "min_price",
    "status",
    "decision_history_id",
    "mark_return_pct",
    "mfe_pct",
    "mae_pct",
    "peak_drawdown_pct",
    "realizable_exit_usdt",
    "realizable_return_pct",
    "exit_state",
    "exit_quality",
    "exit_reason",
    "closed_at",
    "last_exit_probe_at",
    "context_version",
}

_WATCH_SNAPSHOT_COLUMNS = {
    "id",
    "probe_id",
    "decision_history_id",
    "captured_at",
    "version",
    "liquidity_usd",
    "volume_usd",
    "volume_turnover",
    "buys",
    "participant_identity_coverage",
    "origin_participation_coverage",
    "flow_coverage",
    "flow_participant_identity_coverage",
    "native_event_count",
    "market_regime",
    "flow_confirmation",
    "flow_quality",
    "flow_divergence",
    "liquidity_state",
    "market_evidence_ready",
    "participant_evidence_ready",
    "stream_math_state",
    "volatility_state",
    "ewma_volatility",
    "price_log_return",
    "liquidity_log_change",
    "raw_context_json",
}


def _watch_probe_schema_ready(db):
    return (
        _WATCH_PROBE_COLUMNS.issubset(
            _schema_columns(db, "watch_probe_trades")
        )
        and _schema_object_exists(
            db,
            "table",
            "watch_probe_shadow_exits",
        )
        and _schema_object_exists(
            db,
            "index",
            "idx_watch_probe_shadow_exits_probe",
        )
        and _schema_object_exists(
            db,
            "index",
            "idx_watch_probe_trades_status",
        )
    )


def _watch_snapshot_schema_ready(db):
    return (
        _WATCH_SNAPSHOT_COLUMNS.issubset(
            _schema_columns(
                db,
                "watch_probe_entry_snapshots",
            )
        )
        and _schema_object_exists(
            db,
            "index",
            "idx_watch_probe_entry_snapshots_decision",
        )
    )


def _close_failed_store(instance):
    db = getattr(instance, "_db", None)
    if db is None:
        return
    try:
        db.close()
    except sqlite3.Error:
        pass


class _SerializedWatchProbeStore(_OriginalWatchProbeStore):
    _canonical_instance = None
    _canonical_key = None

    def __new__(cls, db_path):
        key = _canonical_paper_db_key(db_path)
        if key is None:
            return super().__new__(cls)

        with _watch_store_init_lock:
            if (
                cls._canonical_instance is None
                or cls._canonical_key != key
            ):
                instance = super().__new__(cls)
                try:
                    _OriginalWatchProbeStore.__init__(instance, db_path)
                except Exception:
                    _close_failed_store(instance)
                    raise
                cls._canonical_instance = instance
                cls._canonical_key = key

            return cls._canonical_instance

    def __init__(self, db_path):
        if _canonical_paper_db_key(db_path) is not None:
            return
        super().__init__(db_path)

    def _ensure_schema(self):
        if (
            _canonical_paper_db_key(
                getattr(self, "db_path", None)
            )
            is not None
            and _watch_probe_schema_ready(self._db)
        ):
            return
        return _OriginalWatchProbeStore._ensure_schema(self)


class _SerializedWatchProbeEntrySnapshotStore(
    _OriginalWatchProbeEntrySnapshotStore
):
    _canonical_instance = None
    _canonical_key = None

    def __new__(cls, db_path):
        key = _canonical_paper_db_key(db_path)
        if key is None:
            return super().__new__(cls)

        with _watch_store_init_lock:
            if (
                cls._canonical_instance is None
                or cls._canonical_key != key
            ):
                instance = super().__new__(cls)
                try:
                    _OriginalWatchProbeEntrySnapshotStore.__init__(
                        instance,
                        db_path,
                    )
                except Exception:
                    _close_failed_store(instance)
                    raise
                cls._canonical_instance = instance
                cls._canonical_key = key

            return cls._canonical_instance

    def __init__(self, db_path):
        if _canonical_paper_db_key(db_path) is not None:
            return
        super().__init__(db_path)

    def _ensure_schema(self):
        if (
            _canonical_paper_db_key(
                getattr(self, "db_path", None)
            )
            is not None
            and _watch_snapshot_schema_ready(self._db)
        ):
            return
        return _OriginalWatchProbeEntrySnapshotStore._ensure_schema(self)


_watch_probe_store.WatchProbeStore = _SerializedWatchProbeStore
_watch_probe_entry_snapshot.WatchProbeEntrySnapshotStore = (
    _SerializedWatchProbeEntrySnapshotStore
)

__all__ = ["ScientificCounterfactualObservationStore"]
