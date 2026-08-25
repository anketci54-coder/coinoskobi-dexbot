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
        discovery_block_span=10, observation_batches_per_cycle=1,
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
    for blocks, batches in (({"pancakeswap_v2": 1}, 1),
                            ({"pancakeswap_v2": 1, "pancakeswap_v3": 1}, 5)):
        try:
            FullUniverseObservationRuntime(
                start_blocks=blocks, registry=object(), log_reader=lambda **kwargs: [],
                finalized_block_reader=lambda: 1, snapshot_client=object(),
                observation_batches_per_cycle=batches,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid shadow bound accepted")


def test_spawn_isolated_uses_worker_owned_rpc(monkeypatch, tmp_path):
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
        "DexScreenerSnapshotClient",
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
