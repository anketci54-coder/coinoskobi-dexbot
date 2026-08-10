from app.filter.ingress_gate import IngressGate
from app.pipeline.candidate_queue import CandidateAdmissionQueue
from app.pipeline.engine import PipelineEngine


class FakeCache:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeManager:
    def process(self):
        return None


def candidate(index, liquidity=10_000):
    return {
        "pool": f"pool-{index}",
        "token": f"bsc_0x{index:040x}",
        "quote_token": (
            "bsc_0x000000000000000000000000"
            "00000000000000ff"
        ),
        "name": f"T{index}",
        "dex": "pancakeswap_v2",
        "liquidity": liquidity,
        "volume_24h": 5_000,
        "buys_24h": 20,
        "fdv": 100_000,
        "price_usd": 0.001,
        "created_at": "2099-01-01T00:00:00+00:00",
        "updated_at": "2099-01-01T00:00:00+00:00",
    }


def test_pipeline_only_sends_active_candidates_to_queue():
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    rows = [
        candidate(1, liquidity=20_000),
        candidate(2, liquidity=100),
    ]

    engine.cache = FakeCache(rows)
    engine.ingress_gate = IngressGate()
    engine.manager = FakeManager()

    engine.candidate_queue = CandidateAdmissionQueue(
        max_pending=1000,
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

    assert len(calls) == 1
    assert calls[0].endswith("1")
