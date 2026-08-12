import asyncio

from app.pipeline.candidate_queue import CandidateAdmissionQueue
from app.dex.runtime_market_flow import RuntimeMarketFlowStore
from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.dex.transaction_origin import TransactionOriginResolver
from app.learning.runtime_outcome_feed import RuntimeLearningOutcomeFeed


PAIR = "0x00000000000000000000000000000000000000aa"
TOKEN = "0x0000000000000000000000000000000000000001"
QUOTE = "0x0000000000000000000000000000000000000002"
WALLET = "0x0000000000000000000000000000000000000123"


def test_candidate_queue_soak():
    q = CandidateAdmissionQueue(
        max_pending=1024,
        cooldown_seconds=20,
    )

    for i in range(200000):
        q.enqueue({
            "chain": "bsc",
            "token": f"token-{i % 5000}",
            "liquidity": float(i % 1000),
            "volume_24h": float(i % 10000),
            "buys_24h": i % 100,
        })

    assert q.pending_count <= 1024

    # OCR bounded implementation must also keep
    # auxiliary structures bounded.
    assert len(q._best_heap) <= 16384
    assert len(q._worst_heap) <= 16384


def test_market_flow_soak():
    store = RuntimeMarketFlowStore(
        max_pairs=8,
        max_events_per_pair=2048,
    )

    store.register_pair(
        PAIR,
        TOKEN,
        QUOTE,
    )

    for i in range(200000):
        store.observe_event({
            "event_identity": f"0x{i:064x}:0x1",
            "transaction_hash": f"0x{i:064x}",
            "address": PAIR,
            "topics": [
                "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
            ],
            "data": (
                "0x"
                + f"{0:064x}"
                + f"{10:064x}"
                + f"{5:064x}"
                + f"{0:064x}"
            ),
        })

    status = store.status()

    assert status["event_count"] == 2048
    assert status["pair_count"] <= 8
    assert status["bounded"] is True


def test_actor_and_resolver_soak():
    resolver = TransactionOriginResolver(
        max_entries=2048,
        fetcher=lambda _: {
            "from": WALLET
        },
    )

    runtime = RuntimeActorIntelligence(
        max_pairs=8,
        max_events_per_pair=2048,
        resolver=resolver,
    )

    async def run():
        for i in range(50000):
            await runtime.observe_event(
                {
                    "event_identity": f"0x{i:064x}:0x1",
                    "transaction_hash": f"0x{i:064x}",
                    "address": PAIR,
                },
                direction=(
                    "BULL"
                    if i % 2 == 0
                    else "BEAR"
                ),
            )

    asyncio.run(run())

    status = runtime.status()

    assert status["event_count"] == 2048
    assert status["pair_count"] <= 8
    assert status["resolver"]["size"] <= 2048
    assert status["bounded"] is True


def test_learning_soak():
    feed = RuntimeLearningOutcomeFeed(
        max_events=2048,
        max_memory=1024,
        max_readmodel=64,
        min_samples=20,
    )

    for i in range(50000):
        feed.observe_paper_close(
            position_id=i,
            token=TOKEN,
            observed_at="2026-01-01T00:00:00+00:00",
            evaluated_at="2026-01-01T00:10:00+00:00",
            entry_price=1.0,
            exit_price=(
                1.1
                if i % 4
                else 0.9
            ),
            realized_return=(
                0.1
                if i % 4
                else -0.1
            ),
            close_reason=(
                "TAKE_PROFIT"
                if i % 4
                else "STOP_LOSS"
            ),
        )

    status = feed.status()

    assert status["event_count"] == 2048
    assert status["memory_size"] <= 1024
    assert status["readmodel_size"] <= 64
    assert status["bounded"] is True
    assert status["automatic_apply_allowed"] is False
    assert status["execution_authority"] is False
