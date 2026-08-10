import threading
import time

from app.pipeline.candidate_queue import (
    CandidateAdmissionQueue,
)
from app.pipeline.work_scheduler import (
    WorkScheduler,
)


def row(
    index,
    chain,
    state="WARM",
):
    return {
        "chain": chain,
        "token": (
            f"0x{index:040x}"
        ),
        "liquidity": 10_000 + index,
        "volume_24h": 5_000 + index,
        "buys_24h": 20 + index,
        "conveyor": {
            "cache_state": state,
            "missing_analyzers": [],
        },
    }


def test_two_chains_round_robin_inside_same_lane():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=0,
    )

    for i in range(10):
        queue.enqueue(
            row(
                i,
                "bsc",
            )
        )

    for i in range(100, 103):
        queue.enqueue(
            row(
                i,
                "mocknet",
            )
        )

    scheduler = WorkScheduler(
        max_workers=1
    )

    seen = []

    scheduler.process_queue(
        queue,
        lambda item: seen.append(
            item["chain"]
        ),
    )

    first_six = seen[:6]

    assert first_six[0] != first_six[1]
    assert first_six[1] != first_six[2]
    assert first_six[2] != first_six[3]
    assert first_six[3] != first_six[4]
    assert first_six[4] != first_six[5]

    assert set(first_six) == {
        "bsc",
        "mocknet",
    }

    assert seen.count("bsc") == 10
    assert seen.count("mocknet") == 3


def test_busy_chain_does_not_starve_small_chain():
    queue = CandidateAdmissionQueue(
        max_pending=10_000,
        cooldown_seconds=0,
    )

    for i in range(1_000):
        queue.enqueue(
            row(
                i,
                "bsc",
            )
        )

    for i in range(10_000, 10_005):
        queue.enqueue(
            row(
                i,
                "mocknet",
            )
        )

    scheduler = WorkScheduler(
        max_workers=1
    )

    seen = []

    scheduler.process_queue(
        queue,
        lambda item: seen.append(
            item["chain"]
        ),
    )

    first_mock = seen.index(
        "mocknet"
    )

    assert first_mock <= 1

    assert seen[:10].count(
        "mocknet"
    ) == 5


def test_single_chain_uses_full_capacity():
    queue = CandidateAdmissionQueue(
        max_pending=1_000,
        cooldown_seconds=0,
    )

    for i in range(100):
        queue.enqueue(
            row(
                i,
                "bsc",
            )
        )

    scheduler = WorkScheduler(
        max_workers=8
    )

    result = scheduler.process_queue(
        queue,
        lambda _: None,
    )

    assert result["processed"] == 100
    assert result["pending"] == 0

    assert (
        result["chains"]["processed"][
            "bsc"
        ]
        == 100
    )


def test_unused_capacity_is_not_reserved_per_chain():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=0,
    )

    for i in range(16):
        queue.enqueue(
            row(
                i,
                "bsc",
            )
        )

    active = 0
    max_active = 0
    lock = threading.Lock()

    def worker(_):
        nonlocal active
        nonlocal max_active

        with lock:
            active += 1
            max_active = max(
                max_active,
                active,
            )

        time.sleep(0.03)

        with lock:
            active -= 1

    scheduler = WorkScheduler(
        max_workers=8
    )

    scheduler.process_queue(
        queue,
        worker,
    )

    assert max_active >= 6


def test_lane_priority_still_beats_chain_fairness():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=0,
    )

    queue.enqueue(
        row(
            1,
            "bsc",
            state="COLD",
        )
    )

    queue.enqueue(
        row(
            2,
            "mocknet",
            state="WARM",
        )
    )

    scheduler = WorkScheduler(
        max_workers=1
    )

    seen = []

    scheduler.process_queue(
        queue,
        lambda item: seen.append(
            (
                item["chain"],
                item["conveyor"][
                    "cache_state"
                ],
            )
        ),
    )

    assert seen[0] == (
        "mocknet",
        "WARM",
    )

    assert seen[1] == (
        "bsc",
        "COLD",
    )
