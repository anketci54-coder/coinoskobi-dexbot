from app.universe.discovery import PANCAKE_FACTORY_STREAMS, PancakeUniverseDiscovery
from app.universe.registry import UniverseRegistry
from app.universe.scheduler import UniverseObservationScheduler
from app.universe.seismic import SeismicClassifier
from app.universe.snapshot import DexScreenerSnapshotClient


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
        self.observer = UniverseObservationScheduler(
            self.registry, snapshot_client or DexScreenerSnapshotClient()
        )
        self.classifier = SeismicClassifier()
        self.confirmation_depth = max(0, int(confirmation_depth))
        self.observation_batches_per_cycle = int(observation_batches_per_cycle)
        if not 1 <= self.observation_batches_per_cycle <= 4:
            raise ValueError("observation batches per cycle must be 1..4")
        self._stream_cursor = 0
        self.cycles = 0

    def run_once(self):
        finalized = max(0, int(self.finalized_block_reader()) - self.confirmation_depth)
        stream = PANCAKE_FACTORY_STREAMS[
            self._stream_cursor % len(PANCAKE_FACTORY_STREAMS)
        ]
        self._stream_cursor += 1
        existing = self.discovery.scan(
            stream, start_block=self.start_blocks[stream["dex"]],
            finalized_block=finalized, branch="EXISTING",
        )
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
            evaluations.append(evaluation)
        self.cycles += 1
        return {
            "state": "SHADOW_READY", "cycle": self.cycles,
            "discovery": {"existing": existing, "new": tail},
            "observation_batches": observation_results,
            "observed": len(observed_pools), "evaluated": len(evaluations),
            "universe_size": self.registry.count(),
            "decision_authority": False, "paper_authority": False,
            "live_authority": False, "wallet_authority": False,
            "execution_authority": False,
        }


__all__ = ["FullUniverseObservationRuntime", "Web3LogReader"]


def bind_shadow_runtime(runner, runtime, *, interval=1):
    interval = int(interval)
    if interval < 1:
        raise ValueError("positive shadow interval required")
    runner.scheduler.every(
        interval=interval, func=runtime.run_once,
        name="full_universe_shadow",
    )
    return {
        "state": "BOUND", "interval": interval,
        "decision_authority": False, "paper_authority": False,
        "live_authority": False, "wallet_authority": False,
        "execution_authority": False,
    }


__all__.append("bind_shadow_runtime")
