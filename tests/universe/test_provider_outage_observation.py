import sqlite3

from app.universe.discovery import PANCAKE_FACTORY_STREAMS
from app.universe.registry import UniverseRegistry
from app.universe.runtime import FullUniverseObservationRuntime


def address(value):
    return "0x" + f"{value:040x}"


class SnapshotClient:
    def __init__(self):
        self.calls = []

    def fetch(self, due):
        self.calls.append(due)
        return [
            {
                "chain": row["chain"],
                "dex": row["dex"],
                "pool": row["pool"],
                "source": "dexscreener",
                "observed_at": "2026-09-03T12:00:00+00:00",
                "price_usd": 1.0,
                "liquidity_usd": 1000.0,
                "volume_m5_usd": 100.0,
                "volume_h24_usd": 1000.0,
                "txns_m5": 10,
                "change_m5": 0.1,
            }
            for row in due
        ]


def test_finalized_block_rpc_outage_does_not_starve_snapshots():
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    stream = PANCAKE_FACTORY_STREAMS[0]
    pool = address(100)

    registry.ingest([
        {
            "chain": "bsc",
            "dex": stream["dex"],
            "pool": pool,
            "token0": address(101),
            "token1": address(102),
            "factory": stream["factory"],
            "creation_block": 1,
            "creation_tx": "0x" + "a" * 64,
            "discovery_branch": "EXISTING",
        }
    ])

    row = dict(
        registry.db.execute(
            "SELECT * FROM universe_pool_registry WHERE pool=?",
            (pool,),
        ).fetchone()
    )
    registry.schedule_observations(
        [(row, "2026-09-03T11:00:00+00:00")]
    )

    snapshots = SnapshotClient()

    def provider_down():
        raise ConnectionError("secret-provider-url-must-not-leak")

    subject = FullUniverseObservationRuntime(
        start_blocks={
            "pancakeswap_v2": 1,
            "pancakeswap_v3": 1,
        },
        registry=registry,
        log_reader=lambda **kwargs: [],
        finalized_block_reader=provider_down,
        snapshot_client=snapshots,
        confirmation_depth=0,
        discovery_batches_per_cycle=1,
        observation_batches_per_cycle=1,
    )

    result = subject.run_once()

    assert result["state"] == "SHADOW_DEGRADED"
    assert result["provider_degraded"] is True
    assert result["discovery"]["existing"]["branch"] == "FINALIZED_BLOCK"
    assert result["discovery"]["existing"]["error"] == "ConnectionError"
    assert result["discovery"]["new"]["state"] == "SKIPPED_PROVIDER_UNAVAILABLE"

    assert len(snapshots.calls) == 1
    assert result["observed"] == 1
    assert result["evaluated"] == 1

    latest = registry.db.execute(
        "SELECT latest_snapshot_at FROM universe_pool_registry WHERE pool=?",
        (pool,),
    ).fetchone()[0]
    assert latest == "2026-09-03T12:00:00+00:00"

    serialized = repr(result)
    assert "secret-provider-url-must-not-leak" not in serialized
