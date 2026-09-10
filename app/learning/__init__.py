"""Learning package bootstrap.

The durable counterfactual store is hardened at package import so existing
runtime imports keep the same public class contract while gaining checkpoint-
first scheduling, exact token+pool identity, scientific horizon-label quality
and a conservative one-USDT economic-capacity label.
"""

import threading
from pathlib import Path

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
# WATCH stores lazily. For the canonical production paper DB, two workers may
# therefore both pass the engine's ``is None`` check before either publishes its
# store. Constructor-only locking is insufficient: it can still leave two live
# store instances with independent runtime locks.
#
# Make each canonical WATCH store a process singleton and initialize that single
# object while holding one shared lock. Every racing constructor call therefore
# returns the same fully initialized object. Test/non-canonical DB paths retain
# normal independent-instance semantics.
_watch_store_init_lock = threading.RLock()
_OriginalWatchProbeStore = _watch_probe_store.WatchProbeStore
_OriginalWatchProbeEntrySnapshotStore = (
    _watch_probe_entry_snapshot.WatchProbeEntrySnapshotStore
)


def _canonical_paper_db_key(db_path):
    try:
        resolved = Path(db_path).resolve(strict=False).as_posix()
    except (TypeError, ValueError, OSError):
        return None

    if not resolved.endswith("/data/paper_trades.db"):
        return None

    return resolved


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
                _OriginalWatchProbeStore.__init__(instance, db_path)
                cls._canonical_instance = instance
                cls._canonical_key = key

            return cls._canonical_instance

    def __init__(self, db_path):
        if _canonical_paper_db_key(db_path) is not None:
            return
        super().__init__(db_path)


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
                _OriginalWatchProbeEntrySnapshotStore.__init__(
                    instance,
                    db_path,
                )
                cls._canonical_instance = instance
                cls._canonical_key = key

            return cls._canonical_instance

    def __init__(self, db_path):
        if _canonical_paper_db_key(db_path) is not None:
            return
        super().__init__(db_path)


_watch_probe_store.WatchProbeStore = _SerializedWatchProbeStore
_watch_probe_entry_snapshot.WatchProbeEntrySnapshotStore = (
    _SerializedWatchProbeEntrySnapshotStore
)

__all__ = ["ScientificCounterfactualObservationStore"]
