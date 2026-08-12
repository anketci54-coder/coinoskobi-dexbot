import app.pipeline.candidate_queue as module

from app.pipeline.candidate_queue import (
    CandidateAdmissionQueue,
)


def row(i, *, liquidity=None):
    return {
        "token": f"0x{i:040x}",
        "chain": "bsc",
        "liquidity": (
            i
            if liquidity is None
            else liquidity
        ),
        "volume_24h": i * 2,
        "buys_24h": i % 100,
    }


def test_duplicate_updates_do_not_leave_unbounded_heaps():
    q = CandidateAdmissionQueue(
        max_pending=64,
        heap_compaction_factor=3,
    )

    base = row(
        1,
        liquidity=100,
    )

    for i in range(100000):
        updated = dict(base)
        updated["liquidity"] = (
            100 + i
        )

        assert q.enqueue(
            updated
        )

    s = q.stats()

    assert s["pending"] == 1

    assert (
        s["best_heap_size"]
        <= q.max_pending
        * q.heap_compaction_factor
    )

    assert (
        s["worst_heap_size"]
        <= q.max_pending
        * q.heap_compaction_factor
    )

    assert (
        s["heap_compactions"]
        > 0
    )


def test_heap_bound_under_mixed_pressure():
    q = CandidateAdmissionQueue(
        max_pending=256,
        heap_compaction_factor=4,
    )

    for i in range(250000):
        identity = i % 1000

        q.enqueue({
            "token": (
                f"0x{identity:040x}"
            ),
            "chain": (
                "bsc"
                if identity % 2 == 0
                else "eth"
            ),
            "liquidity": i,
            "volume_24h": i * 2,
            "buys_24h": i % 200,
        })

    s = q.stats()

    assert s["pending"] <= 256

    assert (
        s["best_heap_size"]
        <= q.max_heap_entries
    )

    assert (
        s["worst_heap_size"]
        <= q.max_heap_entries
    )


def test_expired_cooldowns_are_pruned(monkeypatch):
    now = [1000.0]

    monkeypatch.setattr(
        module.time,
        "monotonic",
        lambda: now[0],
    )

    q = CandidateAdmissionQueue(
        max_pending=16,
        cooldown_seconds=10,
        cooldown_compaction_factor=2,
    )

    for i in range(100):
        q.mark_analyzed(
            f"0x{i:040x}",
            chain="bsc",
        )

        now[0] += 11.0

    q.compact()

    assert q.cooldown_size == 0

    assert (
        q.cooldown_prunes
        > 0
    )


def test_active_cooldowns_remain_effective(monkeypatch):
    now = [1000.0]

    monkeypatch.setattr(
        module.time,
        "monotonic",
        lambda: now[0],
    )

    q = CandidateAdmissionQueue(
        max_pending=16,
        cooldown_seconds=20,
    )

    token = (
        "0x0000000000000000000000000000000000000001"
    )

    q.mark_analyzed(
        token,
        chain="bsc",
    )

    assert q.enqueue({
        "token": token,
        "chain": "bsc",
        "liquidity": 100,
    }) is False

    now[0] += 21

    assert q.enqueue({
        "token": token,
        "chain": "bsc",
        "liquidity": 100,
    }) is True


def test_compact_preserves_priority_behavior():
    q = CandidateAdmissionQueue(
        max_pending=3
    )

    q.enqueue(
        row(
            1,
            liquidity=10,
        )
    )

    q.enqueue(
        row(
            2,
            liquidity=30,
        )
    )

    q.enqueue(
        row(
            3,
            liquidity=20,
        )
    )

    q.compact()

    first = q.pop()
    second = q.pop()
    third = q.pop()

    assert (
        first["liquidity"]
        == 30
    )

    assert (
        second["liquidity"]
        == 20
    )

    assert (
        third["liquidity"]
        == 10
    )


def test_overflow_still_rejects_low_priority():
    q = CandidateAdmissionQueue(
        max_pending=2
    )

    assert q.enqueue(
        row(
            1,
            liquidity=100,
        )
    )

    assert q.enqueue(
        row(
            2,
            liquidity=200,
        )
    )

    assert q.enqueue(
        row(
            3,
            liquidity=50,
        )
    ) is False

    assert q.pending_count == 2


def test_overflow_evicts_worst_for_better_candidate():
    q = CandidateAdmissionQueue(
        max_pending=2
    )

    q.enqueue(
        row(
            1,
            liquidity=100,
        )
    )

    q.enqueue(
        row(
            2,
            liquidity=200,
        )
    )

    assert q.enqueue(
        row(
            3,
            liquidity=300,
        )
    )

    values = [
        q.pop()["liquidity"],
        q.pop()["liquidity"],
    ]

    assert values == [
        300,
        200,
    ]


def test_stats_expose_strict_bounds():
    q = CandidateAdmissionQueue(
        max_pending=32
    )

    s = q.stats()

    assert (
        s["strictly_bounded"]
        is True
    )

    assert (
        s["max_heap_entries"]
        == (
            32
            * q.heap_compaction_factor
        )
    )

    assert (
        s["max_cooldown_entries"]
        == (
            32
            * q.cooldown_compaction_factor
        )
    )

    assert (
        s["trade_permission"]
        is False
    )

    assert (
        s["decision_authority"]
        is False
    )

    assert (
        s["execution_authority"]
        is False
    )

def test_active_cooldowns_are_hard_bounded():
    q = CandidateAdmissionQueue(
        max_pending=128,
        cooldown_seconds=3600,
        cooldown_compaction_factor=4,
    )

    now = 1_000_000.0

    for i in range(10_000):
        q._cooldown_until[
            f"bsc:0x{i:040x}"
        ] = now + 3600 + i

    q._prune_cooldowns(
        now=now,
        force=True,
    )

    stats = q.stats()

    assert (
        stats["cooldown_size"]
        <= stats["max_cooldown_entries"]
    )

    assert (
        stats["max_cooldown_entries"]
        == 512
    )

    assert (
        stats["strictly_bounded"]
        is True
    )
