import time

from app.pipeline.candidate_queue import CandidateAdmissionQueue
from app.pipeline.work_scheduler import WorkScheduler


def row(index):
    return {
        "chain": "bsc",
        "token": f"0x{index:040x}",
        "liquidity": 10_000 + index,
        "volume_24h": 5_000 + index,
        "buys_24h": 20 + index,
    }


def test_scheduler_drains_entire_queue():
    queue = CandidateAdmissionQueue(
        max_pending=1000,
        cooldown_seconds=0,
    )

    queue.enqueue_many(
        [row(i) for i in range(100)]
    )

    seen = []

    scheduler = WorkScheduler(
        max_workers=8
    )

    result = scheduler.process_queue(
        queue,
        lambda item: seen.append(item["token"]),
    )

    assert len(seen) == 100
    assert result["processed"] == 100
    assert result["failed"] == 0
    assert result["pending"] == 0


def test_scheduler_isolates_single_failure():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=0,
    )

    queue.enqueue_many(
        [row(i) for i in range(10)]
    )

    seen = []

    def worker(item):
        seen.append(item["token"])

        if item["token"].endswith("5"):
            raise RuntimeError("boom")

    scheduler = WorkScheduler(
        max_workers=4
    )

    result = scheduler.process_queue(
        queue,
        worker,
    )

    assert len(seen) == 10
    assert result["processed"] == 9
    assert result["failed"] == 1
    assert result["pending"] == 0


def test_scheduler_uses_bounded_parallelism():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=0,
    )

    queue.enqueue_many(
        [row(i) for i in range(8)]
    )

    start = time.perf_counter()

    scheduler = WorkScheduler(
        max_workers=4
    )

    scheduler.process_queue(
        queue,
        lambda _: time.sleep(0.05),
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    assert elapsed < 0.25
