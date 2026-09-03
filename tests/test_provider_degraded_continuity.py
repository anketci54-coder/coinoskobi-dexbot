import sqlite3

from app.api.panel_operations import answer_vezir_query, build_operations_payload
from app.universe.discovery import PANCAKE_FACTORY_STREAMS
from app.universe.registry import UniverseRegistry
from app.universe.runtime import FullUniverseObservationRuntime


def _address(value):
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


def test_finalized_block_provider_failure_does_not_starve_snapshots():
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    stream = PANCAKE_FACTORY_STREAMS[0]
    pool = _address(100)
    registry.ingest([{
        "chain": "bsc",
        "dex": stream["dex"],
        "pool": pool,
        "token0": _address(101),
        "token1": _address(102),
        "factory": stream["factory"],
        "creation_block": 1,
        "creation_tx": "0x" + "b" * 64,
        "discovery_branch": "EXISTING",
    }])
    registry.schedule_observations([(
        dict(registry.db.execute(
            "SELECT * FROM universe_pool_registry WHERE pool=?", (pool,)
        ).fetchone()),
        "2026-09-03T11:00:00+00:00",
    )])

    snapshots = SnapshotClient()

    def unavailable_block():
        raise ConnectionError("provider secret must never leak")

    subject = FullUniverseObservationRuntime(
        start_blocks={"pancakeswap_v2": 1, "pancakeswap_v3": 1},
        registry=registry,
        log_reader=lambda **kwargs: [],
        finalized_block_reader=unavailable_block,
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
    assert result["observed"] == 1
    assert result["evaluated"] == 1
    assert len(snapshots.calls) == 1


def test_vezir_names_provider_problem_and_keeps_authority_closed():
    operations = build_operations_payload(
        runtime_active=True,
        data_healthy=False,
        watch={"open": 3164, "closed": 0, "verified": 0, "limited": 0, "probed": 3164},
        paper={"open": 0, "closed": 0, "net_pnl_usdt": 0},
        decisions=[{"reason": "WATCH", "count": 200}],
    )

    result = answer_vezir_query("Sistemde sorun var mı?", operations)

    assert result["intent"] == "RISK"
    assert "RPC/provider" in result["answer"]
    assert result["evidence"]["provider_problem"] is True
    assert all(value is False for value in result["permissions"].values())


def test_vezir_greeting_is_not_replaced_by_operations_report():
    operations = build_operations_payload(
        runtime_active=True,
        data_healthy=False,
        watch={"open": 3164},
        paper={"open": 0},
        decisions=[],
    )

    result = answer_vezir_query("Selam", operations)

    assert result["intent"] == "GREETING"
    assert result["answer"].startswith("Selam.")
    assert "3164" not in result["answer"]
