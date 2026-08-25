from app.pipeline.candidate_queue import CandidateAdmissionQueue


def row(index, liquidity=None):
    return {
        "token": f"bsc_0x{index:040x}",
        "liquidity": (
            liquidity
            if liquidity is not None
            else 10_000 + index
        ),
        "volume_24h": 5_000 + index,
        "buys_24h": 20 + index,
    }




def test_queue_preserves_all_unique_candidates_until_consumed():
    queue = CandidateAdmissionQueue(
        max_pending=10_000,
        cooldown_seconds=20,
    )

    queue.enqueue_many(
        row(i)
        for i in range(1_000)
    )

    assert queue.pending_count == 1_000

    seen = []

    while True:
        item = queue.pop()

        if item is None:
            break

        seen.append(item["token"])

    assert len(seen) == 1_000
    assert len(set(seen)) == 1_000
    assert queue.pending_count == 0


def test_queue_collapses_duplicate_token():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=20,
    )

    candidate = row(1)

    queue.enqueue(candidate)

    updated = dict(candidate)
    updated["liquidity"] = 99_999

    queue.enqueue(updated)

    assert queue.pending_count == 1
    assert queue.stats()["duplicates_collapsed"] == 1

    selected = queue.pop()

    assert selected["liquidity"] == 99_999


def test_queue_selects_high_priority_candidate():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=20,
    )

    for i in range(50):
        queue.enqueue(row(i))

    sentinel = row(
        999,
        liquidity=9_000_000,
    )

    queue.enqueue(sentinel)

    selected = queue.pop()

    assert (
        selected["token"]
        == CandidateAdmissionQueue.normalize_token(
            sentinel["token"]
        )
    )


def test_analyzed_token_is_skipped_during_cooldown():
    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=60,
    )

    candidate = row(1)

    queue.enqueue(candidate)

    selected = queue.pop()

    queue.mark_analyzed(
        selected["token"]
    )

    accepted = queue.enqueue(candidate)

    assert accepted is False
    assert queue.pending_count == 0
    assert queue.stats()["cooldown_skipped"] == 1


def test_token_normalization_is_idempotent():
    first = CandidateAdmissionQueue.normalize_token(
        "bsc_SENTINEL_0"
    )

    second = CandidateAdmissionQueue.normalize_token(
        first
    )

    assert first == "sentinel_0"
    assert second == first


def test_token_normalization_preserves_internal_underscore():
    result = CandidateAdmissionQueue.normalize_token(
        "custom_token_name"
    )

    assert result == "custom_token_name"


def test_same_address_on_different_chains_is_not_duplicate():
    queue = CandidateAdmissionQueue()

    base = {
        "token": "0xabc",
        "liquidity": 10000,
        "volume_24h": 5000,
        "buys_24h": 20,
    }

    assert queue.enqueue({
        **base,
        "chain": "bsc",
    })

    assert queue.enqueue({
        **base,
        "chain": "ethereum",
    })

    assert queue.pending_count == 2


def test_same_chain_same_address_collapses_duplicate():
    queue = CandidateAdmissionQueue()

    row = {
        "chain": "bsc",
        "token": "0xabc",
        "liquidity": 10000,
        "volume_24h": 5000,
        "buys_24h": 20,
    }

    assert queue.enqueue(row)
    assert queue.enqueue(row)

    assert queue.pending_count == 1
    assert queue.duplicate_collapsed == 1


def test_chain_aware_cooldown_does_not_block_other_chain():
    queue = CandidateAdmissionQueue(
        cooldown_seconds=60
    )

    queue.mark_analyzed(
        "0xabc",
        chain="bsc",
    )

    assert not queue.enqueue({
        "chain": "bsc",
        "token": "0xabc",
        "liquidity": 10000,
        "volume_24h": 5000,
        "buys_24h": 20,
    })

    assert queue.enqueue({
        "chain": "ethereum",
        "token": "0xabc",
        "liquidity": 10000,
        "volume_24h": 5000,
        "buys_24h": 20,
    })


def test_explicit_cold_pool_never_enters_deep_analysis_queue():
    queue = CandidateAdmissionQueue()
    candidate = {
        **row(1), "pool": f"0x{101:040x}",
        "market_state": "COLD", "seismic_score": 99,
    }
    assert queue.enqueue(candidate) is False
    assert queue.pending_count == 0
    assert queue.stats()["cold_skipped"] == 1


def test_hot_precedes_warm_even_when_market_profile_is_smaller():
    queue = CandidateAdmissionQueue()
    warm = {
        **row(1, liquidity=9_000_000), "pool": f"0x{101:040x}",
        "market_state": "WARM", "seismic_score": 50,
    }
    hot = {
        **row(2, liquidity=100), "pool": f"0x{102:040x}",
        "market_state": "HOT", "seismic_score": 5,
    }
    assert queue.enqueue(warm)
    assert queue.enqueue(hot)
    assert queue.pop()["pool"] == hot["pool"]


def test_seismic_score_orders_candidates_within_same_heat_state():
    queue = CandidateAdmissionQueue()
    lower = {
        **row(1, liquidity=9_000_000), "pool": f"0x{101:040x}",
        "market_state": "WARM", "seismic_score": 3,
    }
    higher = {
        **row(2, liquidity=100), "pool": f"0x{102:040x}",
        "market_state": "WARM", "seismic_score": 8,
    }
    queue.enqueue_many([lower, higher])
    assert queue.pop()["pool"] == higher["pool"]


def test_same_token_in_distinct_pools_has_distinct_identity_and_cooldown():
    queue = CandidateAdmissionQueue(cooldown_seconds=60)
    first = {**row(1), "pool": f"0x{101:040x}", "market_state": "WARM"}
    second = {**row(1), "pool": f"0x{102:040x}", "market_state": "WARM"}
    assert queue.enqueue(first)
    assert queue.enqueue(second)
    selected = queue.pop()
    queue.mark_analyzed(
        selected["token"], pool=selected["pool"], chain="bsc"
    )
    assert queue.enqueue(selected) is False
    remaining = second if selected["pool"] == first["pool"] else first
    assert queue.enqueue(remaining)
