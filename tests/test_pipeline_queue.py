from app.pipeline.candidate_queue import CandidateAdmissionQueue
from app.pipeline.engine import PipelineEngine


class FakeCache:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeFilter:
    def filter_all(self, rows):
        return rows


class FakeManager:
    def process(self):
        return None


def candidate(index):
    return {
        "pool": f"0x{index + 1000:040x}",
        "token": f"bsc_0x{index:040x}",
        "quote_token": (
            "bsc_0x000000000000000000000000"
            "00000000000000ff"
        ),
        "dex": "pancakeswap_v2",
        "liquidity": 10_000 + index,
        "volume_24h": 5_000 + index,
        "buys_24h": 20 + index,
        "fdv": 100_000 + index,
        "price_usd": 0.001,
        "created_at": None,
    }


def test_second_cycle_processes_backlog_not_same_first_batch():
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    rows = [
        candidate(i)
        for i in range(40)
    ]

    engine.cache = FakeCache(rows)
    engine.filter = FakeFilter()
    engine.manager = FakeManager()

    engine.candidate_queue = CandidateAdmissionQueue(
        max_pending=1_000,
        cooldown_seconds=60,
    )

    calls = []

    def fake_run(token, market_context=None):
        calls.append(token)

        return {
            "success": True,
        }

    engine.run = fake_run

    engine.run_cycle()

    first_cycle = list(calls)

    assert len(first_cycle) == 40
    assert len(set(first_cycle)) == 40

    engine.run_cycle()

    second_cycle = calls[40:]

    assert second_cycle == []
