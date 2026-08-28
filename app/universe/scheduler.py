from datetime import datetime, timedelta, timezone

from app.universe.display_metadata import persist_snapshot_display_metadata
from app.universe.snapshot import DEXSCREENER_MAX_BATCH


DEFAULT_STATE_INTERVAL_SECONDS = {
    "COLD": 240,
    "WARM": 60,
    "HOT": 15,
}
DEFAULT_MISSING_RETRY_SECONDS = 60


class UniverseObservationScheduler:
    """Bounded due-work orchestration with no decision or trade authority."""

    def __init__(self, registry, snapshot_client, *, intervals=None,
                 missing_retry_seconds=DEFAULT_MISSING_RETRY_SECONDS,
                 now_func=None):
        self.registry = registry
        self.snapshot_client = snapshot_client
        self.intervals = dict(DEFAULT_STATE_INTERVAL_SECONDS)
        self.intervals.update(intervals or {})
        if set(self.intervals) != {"COLD", "WARM", "HOT"}:
            raise ValueError("complete market-state intervals required")
        if any(int(value) < 1 for value in self.intervals.values()):
            raise ValueError("positive state intervals required")
        self.missing_retry_seconds = int(missing_retry_seconds)
        if self.missing_retry_seconds < 1:
            raise ValueError("positive missing retry required")
        self.now_func = now_func or (lambda: datetime.now(timezone.utc))
        self._prefer_depth = True

    @staticmethod
    def _iso(value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def _due_with_history(self, *, now, limit):
        db = getattr(self.registry, "db", None)
        if db is None:
            return []
        rows = db.execute("""
            SELECT *
            FROM universe_pool_registry
            WHERE latest_snapshot_at IS NOT NULL
              AND next_observation_at IS NOT NULL
              AND next_observation_at <= ?
            ORDER BY
                CASE market_state
                    WHEN 'HOT' THEN 0
                    WHEN 'WARM' THEN 1
                    ELSE 2
                END,
                next_observation_at,
                latest_snapshot_at,
                creation_block
            LIMIT ?
        """, (now, int(limit))).fetchall()
        return [dict(row) for row in rows]

    def _select_due(self, *, now, limit):
        # Alternate depth and breadth so a million-row unseen backlog cannot
        # permanently starve the repeated samples required by the seismic
        # classifier, while full-universe first-pass coverage still advances.
        prefer_depth = self._prefer_depth
        self._prefer_depth = not self._prefer_depth

        if prefer_depth:
            due = self._due_with_history(now=now, limit=limit)
            if due:
                return due

        return self.registry.due_observations(now=now, limit=limit)

    def reschedule_for_state(self, row, *, state):
        state = str(state or "").upper()
        if state not in self.intervals:
            raise ValueError("known market state required")
        next_at = self._iso(
            self.now_func()
            + timedelta(seconds=int(self.intervals[state]))
        )
        self.registry.schedule_observations([(row, next_at)])
        return next_at

    def run_once(self, *, limit=DEXSCREENER_MAX_BATCH):
        limit = int(limit)
        if limit < 1 or limit > DEXSCREENER_MAX_BATCH:
            raise ValueError("scheduler limit must be between 1 and 30")

        now = self.now_func()
        now_iso = self._iso(now)
        due = self._select_due(now=now_iso, limit=limit)
        if not due:
            return {
                "state": "IDLE", "requested": 0, "observed": 0,
                "missing": 0, "provider_call": False,
            }

        snapshots = self.snapshot_client.fetch(due)
        due_by_pool = {row["pool"]: row for row in due}
        returned = {row["pool"] for row in snapshots}
        next_times = {}
        for snapshot in snapshots:
            state = due_by_pool[snapshot["pool"]]["market_state"]
            next_times[snapshot["pool"]] = self._iso(
                now + timedelta(seconds=int(self.intervals[state]))
            )
        self.registry.record_observations(
            snapshots, next_observation_at=next_times
        )
        persist_snapshot_display_metadata(
            self.registry.db,
            snapshots,
        )

        missing = [row for row in due if row["pool"] not in returned]
        if missing:
            retry_at = self._iso(
                now + timedelta(seconds=self.missing_retry_seconds)
            )
            self.registry.schedule_observations(
                [(row, retry_at) for row in missing]
            )

        return {
            "state": "OBSERVED", "requested": len(due),
            "observed": len(snapshots), "missing": len(missing),
            "pools": [row["pool"] for row in snapshots],
            "provider_call": True,
        }


__all__ = ["DEFAULT_STATE_INTERVAL_SECONDS", "UniverseObservationScheduler"]
