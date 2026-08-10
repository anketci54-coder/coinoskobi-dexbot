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


def labeled_row(index, state):
    item = row(index)

    item["conveyor"] = {
        "cache_state": state,
        "missing_analyzers": (
            []
            if state == "WARM"
            else (
                ["risk"]
                if state == "PARTIAL"
                else [
                    "token",
                    "pair",
                    "risk",
                ]
            )
        ),
    }

    return item


def test_scheduler_processes_warm_before_cold():
    import threading

    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=0,
    )

    for i in range(8):
        queue.enqueue(
            labeled_row(
                i,
                "COLD",
            )
        )

    for i in range(8, 16):
        queue.enqueue(
            labeled_row(
                i,
                "WARM",
            )
        )

    started = []
    lock = threading.Lock()

    def worker(item):
        with lock:
            started.append(
                item["conveyor"][
                    "cache_state"
                ]
            )

        time.sleep(0.01)

    scheduler = WorkScheduler(
        max_workers=4
    )

    result = scheduler.process_queue(
        queue,
        worker,
    )

    assert result["processed"] == 16
    assert result["pending"] == 0

    assert started[:4] == [
        "WARM",
        "WARM",
        "WARM",
        "WARM",
    ]


def test_scheduler_reports_lane_counts():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=0,
    )

    for i in range(5):
        queue.enqueue(
            labeled_row(
                i,
                "WARM",
            )
        )

    for i in range(5, 8):
        queue.enqueue(
            labeled_row(
                i,
                "PARTIAL",
            )
        )

    for i in range(8, 10):
        queue.enqueue(
            labeled_row(
                i,
                "COLD",
            )
        )

    scheduler = WorkScheduler(
        max_workers=4
    )

    result = scheduler.process_queue(
        queue,
        lambda _: None,
    )

    assert result["warm"]["input"] == 5
    assert result["partial"]["input"] == 3
    assert result["cold"]["input"] == 2

    assert result["warm"]["processed"] == 5
    assert result["partial"]["processed"] == 3
    assert result["cold"]["processed"] == 2


def test_missing_conveyor_state_defaults_to_cold():
    scheduler = WorkScheduler(
        max_workers=2
    )

    assert scheduler.lane(
        row(1)
    ) == "COLD"
