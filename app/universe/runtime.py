import threading
import time

from app.universe.discovery import PANCAKE_FACTORY_STREAMS, PancakeUniverseDiscovery
from app.universe.registry import UniverseRegistry
from app.universe.scheduler import UniverseObservationScheduler
from app.universe.seismic import SeismicClassifier
from app.universe.snapshot import ProviderStickySnapshotClient


def _new_bsc_web3():
    """Create a worker-owned HTTP provider instead of sharing app.chains.bsc.w3."""
    from web3 import Web3
    from app.config.settings import RPC_URL

    if not RPC_URL:
        raise RuntimeError("RPC_URL required for universe shadow")

    return Web3(Web3.HTTPProvider(RPC_URL))


class Web3LogReader:
    def __init__(self, web3):
        self.web3 = web3

    def __call__(self, *, address, topic0, from_block, to_block):
        return self.web3.eth.get_logs({
            "address": self.web3.to_checksum_address(address),
            "topics": [topic0], "fromBlock": int(from_block),
            "toBlock": int(to_block),
        })


class FullUniverseObservationRuntime:
    """Single bounded shadow owner for discovery, snapshots and heat state."""

    def __init__(self, *, start_blocks, registry=None, log_reader=None,
                 finalized_block_reader=None, snapshot_client=None,
                 confirmation_depth=12, discovery_block_span=2000,
                 discovery_batches_per_cycle=8,
                 observation_batches_per_cycle=4):
        required = {stream["dex"] for stream in PANCAKE_FACTORY_STREAMS}
        self.start_blocks = {dex: int(value) for dex, value in dict(start_blocks).items()}
        if set(self.start_blocks) != required or any(
                value < 1 for value in self.start_blocks.values()):
            raise ValueError("explicit positive V2/V3 start blocks required")
        self.registry = registry or UniverseRegistry()
        if log_reader is None or finalized_block_reader is None:
            from app.chains.bsc import w3
            log_reader = log_reader or Web3LogReader(w3)
            finalized_block_reader = finalized_block_reader or (lambda: w3.eth.block_number)
        self.finalized_block_reader = finalized_block_reader
        self.discovery = PancakeUniverseDiscovery(
            self.registry, log_reader, max_block_span=discovery_block_span
        )
        self.discovery_batches_per_cycle = int(discovery_batches_per_cycle)
        if not 1 <= self.discovery_batches_per_cycle <= 8:
            raise ValueError("discovery batches per cycle must be 1..8")
        self.observer = UniverseObservationScheduler(
            self.registry, snapshot_client or ProviderStickySnapshotClient()
        )
        self.classifier = SeismicClassifier()
        self.confirmation_depth = max(0, int(confirmation_depth))
        self.observation_batches_per_cycle = int(observation_batches_per_cycle)
        if not 1 <= self.observation_batches_per_cycle <= 4:
            raise ValueError("observation batches per cycle must be 1..4")
        self._stream_cursor = 0
        self.cycles = 0

    def spawn_isolated(self):
        """Build a worker-owned runtime with its own SQLite/provider objects."""
        worker_web3 = _new_bsc_web3()
        return type(self)(
            start_blocks=dict(self.start_blocks),
            registry=UniverseRegistry(),
            log_reader=Web3LogReader(worker_web3),
            finalized_block_reader=lambda: worker_web3.eth.block_number,
            snapshot_client=ProviderStickySnapshotClient(),
            confirmation_depth=self.confirmation_depth,
            discovery_block_span=self.discovery.max_block_span,
            discovery_batches_per_cycle=self.discovery_batches_per_cycle,
            observation_batches_per_cycle=self.observation_batches_per_cycle,
        )

    def run_once(self):
        finalized = max(0, int(self.finalized_block_reader()) - self.confirmation_depth)
        stream = PANCAKE_FACTORY_STREAMS[
            self._stream_cursor % len(PANCAKE_FACTORY_STREAMS)
        ]
        self._stream_cursor += 1

        existing_batches = []
        for _ in range(self.discovery_batches_per_cycle):
            existing = self.discovery.scan(
                stream, start_block=self.start_blocks[stream["dex"]],
                finalized_block=finalized, branch="EXISTING",
            )
            existing_batches.append(existing)
            if existing["state"] == "CAUGHT_UP":
                break

        tail = self.discovery.scan(
            stream, start_block=finalized, finalized_block=finalized, branch="NEW",
        )
        observation_results, observed_pools = [], []
        for _ in range(self.observation_batches_per_cycle):
            result = self.observer.run_once()
            observation_results.append(result)
            observed_pools.extend(result.get("pools") or [])
            if result["state"] == "IDLE":
                break
        evaluations = []
        for pool in dict.fromkeys(observed_pools):
            registry_row = self.registry.db.execute("""
                SELECT * FROM universe_pool_registry WHERE pool=?
                ORDER BY latest_snapshot_at DESC LIMIT 1
            """, (pool,)).fetchone()
            if registry_row is None:
                continue
            registry_row = dict(registry_row)
            history = self.registry.observation_history(
                registry_row["chain"], registry_row["dex"], pool, limit=65
            )
            evaluation = self.classifier.classify(
                chain=registry_row["chain"], dex=registry_row["dex"],
                pool=pool, market_state=registry_row["market_state"], history=history,
            )
            self.registry.apply_seismic_evaluation(evaluation)
            if evaluation["next_state"] != evaluation["previous_state"]:
                self.observer.reschedule_for_state(
                    registry_row,
                    state=evaluation["next_state"],
                )
            evaluations.append(evaluation)
        self.cycles += 1
        return {
            "state": "SHADOW_READY", "cycle": self.cycles,
            "discovery": {
                "existing": existing_batches[-1],
                "existing_batches": existing_batches,
                "new": tail,
            },
            "observation_batches": observation_results,
            "observed": len(observed_pools), "evaluated": len(evaluations),
            "universe_size": self.registry.count(),
            "decision_authority": False, "paper_authority": False,
            "live_authority": False, "wallet_authority": False,
            "execution_authority": False,
        }


class UniverseShadowService:
    """Background owner that keeps slow universe/provider work off Runner.tick()."""

    def __init__(self, runtime, *, interval=1, join_timeout=5.0):
        interval = float(interval)
        if interval <= 0:
            raise ValueError("positive shadow interval required")
        self.runtime_template = runtime
        self.interval = interval
        self.join_timeout = max(0.1, float(join_timeout))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._runtime = None
        self.start_count = 0
        self.stop_count = 0
        self.cycle_count = 0
        self.failure_count = 0
        self.last_result = None
        self.last_error = None

    @property
    def name(self):
        return "full_universe_shadow"

    def _build_runtime(self):
        spawn = getattr(self.runtime_template, "spawn_isolated", None)
        if callable(spawn):
            return spawn()
        return self.runtime_template

    def _thread_main(self):
        try:
            runtime = self._build_runtime()
            with self._lock:
                self._runtime = runtime
        except Exception as exc:
            with self._lock:
                self.failure_count += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
            return

        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                result = runtime.run_once()
                with self._lock:
                    self.cycle_count += 1
                    self.last_result = result
                    self.last_error = None
            except Exception as exc:
                with self._lock:
                    self.failure_count += 1
                    self.last_error = f"{type(exc).__name__}: {exc}"

            elapsed = time.monotonic() - started
            self._stop_event.wait(max(0.0, self.interval - elapsed))

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self.last_error = None
            thread = threading.Thread(
                target=self._thread_main,
                name="coinoskobi-universe-shadow",
                daemon=True,
            )
            self._thread = thread
            self.start_count += 1
            thread.start()
            return True

    def stop(self):
        with self._lock:
            thread = self._thread
            if thread is None:
                return False
            self._stop_event.set()

        thread.join(self.join_timeout)
        stopped = not thread.is_alive()
        with self._lock:
            if stopped:
                self.stop_count += 1
                self._thread = None
                self._runtime = None
        return stopped

    def status(self):
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            return {
                "name": self.name,
                "state": "READY" if running else "STOPPED",
                "running": running,
                "interval": self.interval,
                "cycles": self.cycle_count,
                "failures": self.failure_count,
                "last_error": self.last_error,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            }


def bind_shadow_runtime(runner, runtime, *, interval=1):
    service = UniverseShadowService(runtime, interval=interval)
    runner.services.append(service)
    return {
        "state": "BOUND", "interval": int(interval),
        "mode": "BACKGROUND_SERVICE",
        "decision_authority": False, "paper_authority": False,
        "live_authority": False, "wallet_authority": False,
        "execution_authority": False,
    }


__all__ = [
    "FullUniverseObservationRuntime",
    "UniverseShadowService",
    "Web3LogReader",
    "bind_shadow_runtime",
]
