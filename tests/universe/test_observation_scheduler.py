from datetime import datetime, timezone

import pytest

from app.universe.registry import UniverseRegistry
from app.universe.scheduler import UniverseObservationScheduler


def address(value):
    return "0x" + f"{value:040x}"


def pool_row(value, *, dex="pancakeswap_v2", branch="EXISTING"):
    return {
        "chain": "bsc", "dex": dex, "pool": address(value),
        "token0": address(100), "token1": address(200),
        "factory": address(300), "creation_block": value,
        "discovery_branch": branch,
    }


def snapshot(value, *, dex="pancakeswap_v2"):
    return {
        "chain": "bsc", "dex": dex, "pool": address(value),
        "source": "dexscreener", "observed_at": "2026-08-25T16:00:00+00:00",
        "price_usd": 1.25, "liquidity_usd": 5000,
        "volume_h24_usd": 9000, "txns_m5": 5, "txns_h1": 20,
        "txns_h6": 50, "txns_h24": 100, "change_m5": 0.5,
        "change_h1": 2, "change_h6": 4, "change_h24": 8,
    }


class Client:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def fetch(self, due):
        self.calls.append(due)
        return list(self.rows)


class EchoClient:
    def __init__(self):
        self.calls = []

    def fetch(self, due):
        self.calls.append(due)
        return [snapshot(int(row["pool"], 16), dex=row["dex"]) for row in due]


def test_raw_observation_is_appended_and_latest_profile_updates(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row(1)])
    registry.record_observations(
        [snapshot(1)], next_observation_at={
            address(1): "2026-08-25T16:04:00+00:00"
        }
    )
    row = registry.get_pool("bsc", "pancakeswap_v2", address(1))
    assert row["latest_price_usd"] == 1.25
    assert row["latest_snapshot_source"] == "dexscreener"
    assert row["next_observation_at"] == "2026-08-25T16:04:00+00:00"
    assert registry.db.execute(
        "SELECT COUNT(*) FROM universe_market_observation_v1"
    ).fetchone()[0] == 1


def test_unregistered_snapshot_rolls_back_whole_batch(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row(1)])
    with pytest.raises(ValueError, match="not registered"):
        registry.record_observations(
            [snapshot(1), snapshot(2)],
            next_observation_at={
                address(1): "2026-08-25T16:04:00+00:00",
                address(2): "2026-08-25T16:04:00+00:00",
            },
        )
    assert registry.db.execute(
        "SELECT COUNT(*) FROM universe_market_observation_v1"
    ).fetchone()[0] == 0


def test_scheduler_is_bounded_and_uses_state_cadence(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row(1), pool_row(2)])
    registry.db.execute(
        "UPDATE universe_pool_registry SET market_state='WARM' WHERE pool=?",
        (address(2),),
    )
    registry.db.commit()
    client = Client([snapshot(1), snapshot(2)])
    now = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    result = UniverseObservationScheduler(
        registry, client, now_func=lambda: now
    ).run_once(limit=2)
    assert result == {
        "state": "OBSERVED", "requested": 2, "observed": 2,
        "missing": 0, "pools": [address(1), address(2)],
        "provider_call": True,
    }
    assert registry.get_pool("bsc", "pancakeswap_v2", address(1))[
        "next_observation_at"] == "2026-08-25T16:04:00+00:00"
    assert registry.get_pool("bsc", "pancakeswap_v2", address(2))[
        "next_observation_at"] == "2026-08-25T16:01:00+00:00"


def test_depth_and_breadth_alternate_under_large_unseen_backlog(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row(value) for value in range(1, 8)])
    registry.record_observations(
        [snapshot(7)],
        next_observation_at={address(7): "2026-08-25T15:59:00+00:00"},
    )

    client = EchoClient()
    now = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    scheduler = UniverseObservationScheduler(
        registry, client, now_func=lambda: now
    )

    depth = scheduler.run_once(limit=1)
    breadth = scheduler.run_once(limit=1)

    assert depth["pools"] == [address(7)]
    assert breadth["pools"] == [address(1)]
    assert len(client.calls[0]) == 1
    assert len(client.calls[1]) == 1
    assert client.calls[0][0]["latest_snapshot_at"] is not None
    assert client.calls[1][0]["latest_snapshot_at"] is None


def test_new_unseen_pools_get_first_breadth_pick_newest_first(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([
        pool_row(1, branch="EXISTING"),
        pool_row(2, branch="EXISTING"),
        pool_row(100, branch="NEW"),
        pool_row(101, branch="NEW"),
    ])

    client = EchoClient()
    now = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    scheduler = UniverseObservationScheduler(
        registry, client, now_func=lambda: now
    )

    result = scheduler.run_once(limit=2)

    assert result["pools"] == [address(101), address(100)]
    assert [row["discovery_branch"] for row in client.calls[0]] == [
        "NEW", "NEW"
    ]


def test_existing_unseen_lane_cannot_starve_under_continuous_new_backlog(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([
        pool_row(1, branch="EXISTING"),
        pool_row(2, branch="EXISTING"),
        pool_row(100, branch="NEW"),
        pool_row(101, branch="NEW"),
        pool_row(102, branch="NEW"),
    ])

    client = EchoClient()
    now = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    scheduler = UniverseObservationScheduler(
        registry, client, now_func=lambda: now
    )

    first_breadth = scheduler.run_once(limit=1)
    second_breadth = scheduler.run_once(limit=1)

    assert first_breadth["pools"] == [address(102)]
    assert second_breadth["pools"] == [address(1)]
    assert client.calls[0][0]["discovery_branch"] == "NEW"
    assert client.calls[1][0]["discovery_branch"] == "EXISTING"


def test_missing_provider_row_is_deferred_without_fake_history(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row(1)])
    now = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)
    result = UniverseObservationScheduler(
        registry, Client([]), now_func=lambda: now
    ).run_once()
    assert result["missing"] == 1
    assert registry.get_pool("bsc", "pancakeswap_v2", address(1))[
        "next_observation_at"] == "2026-08-25T16:01:00+00:00"
    assert registry.db.execute(
        "SELECT COUNT(*) FROM universe_market_observation_v1"
    ).fetchone()[0] == 0


def test_idle_cycle_and_invalid_limit_make_no_provider_call(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    client = Client([])
    scheduler = UniverseObservationScheduler(registry, client)
    assert scheduler.run_once()["state"] == "IDLE"
    with pytest.raises(ValueError, match="between 1 and 30"):
        scheduler.run_once(limit=31)
    assert client.calls == []
