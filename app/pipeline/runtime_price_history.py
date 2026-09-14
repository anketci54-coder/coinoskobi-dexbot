import threading


class RuntimePriceHistory(dict):
    """Bounded LRU cache for measured runtime price histories.

    Existing keys are refreshed on ``setdefault`` because the pipeline uses
    that operation as its canonical history lookup. Watched token/pool pairs
    are protected from ordinary eviction so empirical-movement candidates can
    actually accumulate observations across scanner churn.
    """

    def __init__(
        self,
        *,
        max_entries=2048,
        watch_snapshot=None,
    ):
        super().__init__()
        self.max_entries = max(1, int(max_entries))
        self.watch_snapshot = watch_snapshot
        self._lock = threading.RLock()

    def _watched_pairs(self):
        loader = self.watch_snapshot
        if not callable(loader):
            return set()

        try:
            snapshot = loader() or {}
        except Exception:
            return set()

        return {
            (
                str(token or "").strip().lower(),
                str(pool or "").strip().lower(),
            )
            for token, pool in snapshot.items()
            if token and pool
        }

    def _evict_if_needed(self):
        watched = self._watched_pairs()

        while len(self) > self.max_entries:
            victim = None

            for key in self:
                try:
                    token, pool, _ = key
                except (TypeError, ValueError):
                    victim = key
                    break

                if (
                    str(token).strip().lower(),
                    str(pool).strip().lower(),
                ) not in watched:
                    victim = key
                    break

            if victim is None:
                victim = next(iter(self))

            super().pop(victim, None)

    def setdefault(self, key, default=None):
        with self._lock:
            if key in self:
                value = super().pop(key)
                super().__setitem__(key, value)
                return value

            value = default
            super().__setitem__(key, value)
            self._evict_if_needed()
            return value


def install_runtime_price_history_cache():
    """Install the production cache without changing decision authority."""
    from app.pipeline import engine as engine_module

    current = getattr(
        engine_module,
        "_RUNTIME_PRICE_HISTORY",
        None,
    )

    if isinstance(current, RuntimePriceHistory):
        return current

    cache = RuntimePriceHistory(
        max_entries=2048,
        watch_snapshot=(
            engine_module._runtime_observation_watch_snapshot
        ),
    )

    if isinstance(current, dict):
        for key, value in current.items():
            cache[key] = value
        cache._evict_if_needed()

    engine_module._RUNTIME_PRICE_HISTORY = cache
    return cache
