import logging
import sqlite3
import threading
import time

import app.universe.runtime as runtime_module
from app.universe.discovery import PANCAKE_FACTORY_STREAMS, PAIR_CREATED_TOPIC
from app.universe.registry import UniverseRegistry
from app.universe.runtime import (
    FullUniverseObservationRuntime,
    UniverseShadowService,
    Web3LogReader,
    bind_shadow_runtime,
)


def address(value): return "0x" + f"{value:040x}"
def topic_address(value): return "0x" + "0" * 24 + f"{value:040x}"
def word(value): return f"{value:064x}"


class LogReader:
    def __init__(self): self.calls = []
    def __call__(self, **request):
        self.calls.append(request)
        if request["topic0"] == PAIR_CREATED_TOPIC and request["from_block"] == 1:
            return [{"topics": [PAIR_CREATED_TOPIC, topic_address(1), topic_address(2)],
                     "data": "0x" + word(3) + word(1), "blockNumber": 1,
                     "transactionHash": "0x" + "a" * 64}]
        return []


class SnapshotClient:
    def __init__(self): self.calls = []
    def fetch(self, due):
        self.calls.append(due)
        return [{"chain": row["chain"], "dex": row["dex"], "pool": row["pool"],
                 "source": "dexscreener", "observed_at": "2026-08-25T16:00:00+00:00",
                 "price_usd": 1, "liquidity_usd": 1000,
                 "volume_m5_usd": 100, "volume_h24_usd": 1000,
                 "txns_m5": 10, "change_m5": 0.1} for row in due]


def runtime(registry, reader):
    return FullUniverseObservationRuntime(
        start_blocks={"pancakeswap_v2": 1, "pancakeswap_v3": 1},
        registry=registry, log_reader=reader, finalized_block_reader=lambda: 20,
        snapshot_client=SnapshotClient(), confirmation_depth=0,
        discovery_block_span=10, discovery_batches_per_cycle=1,
        observation_batches_per_cycle=1,
    )


def test_shadow_runtime_keeps_existing_and_new_checkpoints_independent():
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    reader = LogReader(); result = runtime(registry, reader).run_once()
    stream = PANCAKE_FACTORY_STREAMS[0]
    existing = registry.checkpoint("bsc", stream["dex"], stream["factory"],
                                   stream["event_kind"], "EXISTING")
    new = registry.checkpoint("bsc", stream["dex"], stream["factory"],
                              stream["event_kind"], "NEW")
    assert existing["last_scanned_block"] == 10
    assert new["last_scanned_block"] == 20
    assert result["state"] == "SHADOW_READY"
    assert result["universe_size"] == 1 and result["evaluated"] == 1
    assert result["decision_authority"] is False


def test_shadow_runtime_round_robins_v2_and_v3():
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    reader = LogReader(); subject = runtime(registry, reader)
    subject.run_once(); subject.run_once()
    assert reader.calls[0]["address"].lower() == PANCAKE_FACTORY_STREAMS[0]["factory"].lower()
    assert reader.calls[2]["address"].lower() == PANCAKE_FACTORY_STREAMS[1]["factory"].lower()


def test_shadow_runtime_requires_explicit_start_blocks_and_bounded_batches():
    cases = (
        ({"pancakeswap_v2": 1}, 1, 1),
        ({"pancakeswap_v2": 1, "pancakeswap_v3": 1}, 0, 1),
        ({"pancakeswap_v2": 1, "pancakeswap_v3": 1}, 9, 1),
        ({"pancakeswap_v2": 1, "pancakeswap_v3": 1}, 1, 5),
    )
    for blocks, discovery_batches, observation_batches in cases:
        try:
            FullUniverseObservationRuntime(
                start_blocks=blocks, registry=object(), log_reader=lambda **kwargs: [],
                finalized_block_reader=lambda: 1, snapshot_client=object(),
                discovery_batches_per_cycle=discovery_batches,
                observation_batches_per_cycle=observation_batches,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid shadow bound accepted")


def test_backfill_batches_keep_each_rpc_span_bounded_and_tail_current():
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    reader = LogReader()
    subject = FullUniverseObservationRuntime(
        start_blocks={"pancakeswap_v2": 1, "pancakeswap_v3": 1},
        registry=registry,
        log_reader=reader,
        finalized_block_reader=lambda: 20,
        snapshot_client=SnapshotClient(),
        confirmation_depth=0,
        discovery_block_span=5,
        discovery_batches_per_cycle=3,
        observation_batches_per_cycle=1,
    )

    result = subject.run_once()
    stream = PANCAKE_FACTORY_STREAMS[0]
    existing = registry.checkpoint(
        "bsc", stream["dex"], stream["factory"], stream["event_kind"], "EXISTING"
    )
    new = registry.checkpoint(
        "bsc", stream["dex"], stream["factory"], stream["event_kind"], "NEW"
    )

    existing_calls = reader.calls[:3]
    assert [(row["from_block"], row["to_block"]) for row in existing_calls] == [
        (1, 5), (6, 10), (11, 15)
    ]
    assert all(row["to_block"] - row["from_block"] + 1 <= 5 for row in existing_calls)
    assert reader.calls[3]["from_block"] == 20
    assert reader.calls[3]["to_block"] == 20
    assert existing["last_scanned_block"] == 15
    assert new["last_scanned_block"] == 20
    assert len(result["discovery"]["existing_batches"]) == 3
    assert result["discovery"]["existing"]["state"] == "PARTIAL"
    assert result["discovery"]["existing"]["to_block"] == 15
    assert result["decision_authority"] is False


def test_discovery_failure_does_not_starve_existing_observations(caplog):
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    stream = PANCAKE_FACTORY_STREAMS[0]
    pool = address(100)
    registry.ingest([{
        "chain": "bsc",
        "dex": stream["dex"],
        "pool": pool,
        "token0": address(101),
        "token1": address(102),
        "factory": stream["factory"],
        "creation_block": 1,
        "creation_tx": "0x" + "b" * 64,
        "discovery_branch": "EXISTING",
    }])
    registry.schedule_observations([(
        dict(registry.db.execute(
            "SELECT * FROM universe_pool_registry WHERE pool=?", (pool,)
        ).fetchone()),
        "2026-08-25T15:00:00+00:00",
    )])

    class FailingLogReader:
        def __call__(self, **request):
            raise RuntimeError("provider unavailable")

    snapshots = SnapshotClient()
    subject = FullUniverseObservationRuntime(
        start_blocks={"pancakeswap_v2": 1, "pancakeswap_v3": 1},
        registry=registry,
        log_reader=FailingLogReader(),
        finalized_block_reader=lambda: 20,
        snapshot_client=snapshots,
        confirmation_depth=0,
        discovery_block_span=10,
        discovery_batches_per_cycle=1,
        observation_batches_per_cycle=1,
    )

    with caplog.at_level(logging.WARNING):
        result = subject.run_once()

    assert result["state"] == "SHADOW_DEGRADED"
    assert result["discovery"]["existing"]["state"] == "ERROR"
    assert result["discovery"]["new"]["state"] == "SKIPPED_AFTER_DISCOVERY_ERROR"
    assert result["observed"] == 1
    assert result["evaluated"] == 1
    assert len(snapshots.calls) == 1
    assert registry.db.execute(
        "SELECT latest_snapshot_at FROM universe_pool_registry WHERE pool=?", (pool,)
    ).fetchone()[0] == "2026-08-25T16:00:00+00:00"
    assert "Universe discovery failed" in caplog.text


def test_spawn_isolated_uses_worker_owned_rpc_and_sticky_provider(monkeypatch):
    class Eth:
        block_number = 123
    class WorkerWeb3:
        eth = Eth()

    worker_web3 = WorkerWeb3()
    created = []
    monkeypatch.setattr(
        runtime_module,
        "_new_bsc_web3",
        lambda: created.append(worker_web3) or worker_web3,
    )
    monkeypatch.setattr(
        runtime_module,
        "UniverseRegistry",
        lambda: UniverseRegistry(
            connection=sqlite3.connect(":memory:")
        ),
    )
    monkeypatch.setattr(
        runtime_module,
        "ProviderStickySnapshotClient",
        SnapshotClient,
    )

    template = runtime(
        UniverseRegistry(connection=sqlite3.connect(":memory:")),
        LogReader(),
    )
    isolated = template.spawn_isolated()

    assert created == [worker_web3]
    assert isinstance(isolated.discovery.log_reader, Web3LogReader)
    assert isolated.discovery.log_reader.web3 is worker_web3
    assert isolated.finalized_block_reader() == 123
    assert isolated.registry is not template.registry
    assert isinstance(isolated.observer.snapshot_client, SnapshotClient)
    assert isolated.discovery_batches_per_cycle == template.discovery_batches_per_cycle


def test_shadow_binding_uses_background_service_and_not_scheduler():
    calls = []
    class Scheduler:
        def every(self, **kwargs): calls.append(kwargs)
    class Runner:
        scheduler = Scheduler()
        services = []
    class Runtime:
        def run_once(self): return {"state": "SHADOW_READY"}
    runner = Runner()
    result = bind_shadow_runtime(runner, Runtime(), interval=1)
    assert calls == []
    assert len(runner.services) == 1
    assert isinstance(runner.services[0], UniverseShadowService)
    assert result["state"] == "BOUND"
    assert result["mode"] == "BACKGROUND_SERVICE"
    assert result["decision_authority"] is False


def test_shadow_service_uses_spawned_runtime_and_stops_cleanly():
    ran = threading.Event()
    template_called = []
    spawn_threads = []

    class WorkerRuntime:
        def run_once(self):
            ran.set()
            return {"state": "SHADOW_READY"}

    class TemplateRuntime:
        def spawn_isolated(self):
            spawn_threads.append(threading.current_thread().name)
            return WorkerRuntime()
        def run_once(self):
            template_called.append(True)

    service = UniverseShadowService(TemplateRuntime(), interval=60)
    assert service.start() is True
    assert ran.wait(1.0) is True
    assert service.stop() is True
    assert template_called == []
    assert spawn_threads == ["coinoskobi-universe-shadow"]
    status = service.status()
    assert status["running"] is False
    assert status["cycles"] >= 1
    assert status["decision_authority"] is False


def test_shadow_service_logs_cycle_failures(caplog):
    ran = threading.Event()

    class FailingRuntime:
        def run_once(self):
            ran.set()
            raise RuntimeError("cycle boom")

    service = UniverseShadowService(FailingRuntime(), interval=60)
    with caplog.at_level(logging.WARNING):
        assert service.start() is True
        assert ran.wait(1.0) is True
        for _ in range(50):
            if service.status()["failures"] >= 1:
                break
            time.sleep(0.01)
        assert service.stop() is True

    status = service.status()
    assert status["failures"] >= 1
    assert status["last_error"] == "RuntimeError: cycle boom"
    assert "Universe shadow cycle failed" in caplog.text


def test_slow_shadow_cycle_does_not_block_caller_thread():
    entered = threading.Event()
    release = threading.Event()

    class SlowRuntime:
        def run_once(self):
            entered.set()
            release.wait(1.0)
            return {"state": "SHADOW_READY"}

    service = UniverseShadowService(SlowRuntime(), interval=60)
    started = time.monotonic()
    assert service.start() is True
    assert entered.wait(0.5) is True
    elapsed = time.monotonic() - started
    assert elapsed < 0.5
    release.set()
    assert service.stop() is True
