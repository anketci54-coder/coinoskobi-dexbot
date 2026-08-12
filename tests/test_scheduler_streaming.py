from types import GeneratorType

from app.pipeline.candidate_queue import (
    CandidateAdmissionQueue,
)
from app.pipeline.work_scheduler import (
    WorkScheduler,
)


def row(index, lane="COLD", chain="bsc"):
    return {
        "chain": chain,
        "token": f"0x{index:040x}",
        "liquidity": 10000 + index,
        "volume_24h": 5000 + index,
        "buys_24h": 20 + index,
        "conveyor": {
            "cache_state": lane,
        },
    }


def test_ordered_rows_is_generator():
    scheduler = WorkScheduler(2)

    lanes = {
        "WARM": {
            "bsc": __import__(
                "collections"
            ).deque([row(1, "WARM")]),
        },
        "PARTIAL": {},
        "COLD": {},
    }

    ordered = scheduler._ordered_rows(lanes)

    assert isinstance(
        ordered,
        GeneratorType,
    )


def test_scheduler_still_processes_all_rows():
    q = CandidateAdmissionQueue(
        max_pending=1000,
        cooldown_seconds=0,
    )

    q.enqueue_many([
        row(i, ("WARM", "PARTIAL", "COLD")[i % 3])
        for i in range(500)
    ])

    seen = []

    result = WorkScheduler(
        max_workers=8
    ).process_queue(
        q,
        lambda item: seen.append(
            item["token"]
        ),
    )

    assert result["processed"] == 500
    assert result["failed"] == 0
    assert result["pending"] == 0
    assert len(seen) == 500


def test_chain_round_robin_is_preserved():
    scheduler = WorkScheduler(2)

    from collections import deque

    queues = {
        "bsc": deque([
            row(1, "WARM", "bsc"),
            row(2, "WARM", "bsc"),
        ]),
        "eth": deque([
            row(3, "WARM", "eth"),
            row(4, "WARM", "eth"),
        ]),
    }

    rows = list(
        scheduler._round_robin_rows(
            queues
        )
    )

    assert [
        x["chain"]
        for x in rows
    ] == [
        "bsc",
        "eth",
        "bsc",
        "eth",
    ]
