"""Learning package bootstrap.

The durable counterfactual store is hardened at package import so existing
runtime imports keep the same public class contract while gaining checkpoint-
first scheduling, exact token+pool identity, scientific horizon-label quality
and a conservative one-USDT economic-capacity label.
"""

import threading

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


# Candidate analysis is concurrent. The WATCH stores are intentionally lazy in
# PipelineEngine, so several worker threads can otherwise race their first
# constructors and concurrently execute SQLite schema DDL against the same
# paper DB. Serialize only that one-time constructor/schema section. Runtime
# reads/writes keep each store's existing independent lock and WAL behavior.
_watch_store_init_lock = threading.RLock()
_OriginalWatchProbeStore = _watch_probe_store.WatchProbeStore
_OriginalWatchProbeEntrySnapshotStore = (
    _watch_probe_entry_snapshot.WatchProbeEntrySnapshotStore
)


class _SerializedWatchProbeStore(_OriginalWatchProbeStore):
    def __init__(self, *args, **kwargs):
        with _watch_store_init_lock:
            super().__init__(*args, **kwargs)


class _SerializedWatchProbeEntrySnapshotStore(
    _OriginalWatchProbeEntrySnapshotStore
):
    def __init__(self, *args, **kwargs):
        with _watch_store_init_lock:
            super().__init__(*args, **kwargs)


_watch_probe_store.WatchProbeStore = _SerializedWatchProbeStore
_watch_probe_entry_snapshot.WatchProbeEntrySnapshotStore = (
    _SerializedWatchProbeEntrySnapshotStore
)

__all__ = ["ScientificCounterfactualObservationStore"]
