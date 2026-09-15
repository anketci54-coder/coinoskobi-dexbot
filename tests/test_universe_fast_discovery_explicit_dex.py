from app.pipeline.fast_watch_revisit import (
    DEX_PANCAKESWAP_V2,
    FastWatchRevisitJob,
)


class Scanner:
    def __init__(self):
        self.received = None

    def pool_snapshots(
        self,
        pools,
        *,
        max_pools,
        persist_followups,
    ):
        self.received = pools
        return []


class Ingress:
    def classify_many(self, rows):
        return {"active": []}


class Pipeline:
    def __init__(self):
        self.scanner = Scanner()
        self.ingress_gate = Ingress()


def test_discovery_identity_passes_explicit_dex_to_broker():
    pipeline = Pipeline()
    job = FastWatchRevisitJob(pipeline)

    token = "0x0000000000000000000000000000000000000011"
    pool = "0x0000000000000000000000000000000000000022"

    rows = job._fresh_rows([
        (
            token,
            pool,
            DEX_PANCAKESWAP_V2,
        )
    ])

    assert rows == []
    assert pipeline.scanner.received == [{
        "pool": pool,
        "dex": DEX_PANCAKESWAP_V2,
    }]


def test_legacy_watch_identity_keeps_cache_resolution_path():
    pipeline = Pipeline()
    job = FastWatchRevisitJob(pipeline)

    token = "0x0000000000000000000000000000000000000033"
    pool = "0x0000000000000000000000000000000000000044"

    rows = job._fresh_rows([
        (
            token,
            pool,
        )
    ])

    assert rows == []
    assert pipeline.scanner.received == [pool]
