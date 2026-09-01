
def test_snapshot_provider_failure_degrades_and_reschedules():
    from datetime import datetime, timezone

    from app.universe.scheduler import (
        UniverseObservationScheduler,
    )

    class FakeDB:
        pass

    class FakeRegistry:
        def __init__(self):
            self.db = FakeDB()
            self.scheduled = []

        def schedule_observations(self, rows):
            self.scheduled.extend(rows)

    class FailingSnapshotClient:
        def fetch(self, pools):
            raise RuntimeError("provider unavailable")

    registry = FakeRegistry()

    scheduler = UniverseObservationScheduler(
        registry,
        FailingSnapshotClient(),
        now_func=lambda: datetime(
            2026, 9, 1, tzinfo=timezone.utc
        ),
    )

    due = [{
        "pool": "0xabc",
        "market_state": "COLD",
    }]

    scheduler._select_due = lambda **kwargs: due

    result = scheduler.run_once(limit=1)

    assert result["state"] == "DEGRADED"
    assert result["requested"] == 1
    assert result["observed"] == 0
    assert result["missing"] == 1
    assert result["provider_call"] is True
    assert result["error_class"] == "RuntimeError"
    assert len(registry.scheduled) == 1
