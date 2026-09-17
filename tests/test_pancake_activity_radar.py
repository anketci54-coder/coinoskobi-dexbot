import sqlite3

from app.universe.pancake_activity import (
    PANCAKE_ACTIVITY_TOPICS,
    PANCAKE_V3_SWAP_TOPIC,
    PancakeActivityRadar,
    Web3TopicLogReader,
)


V2_POOL = "0x" + "11" * 20
V3_POOL = "0x" + "22" * 20
UNI_POOL = "0x" + "33" * 20
UNKNOWN_POOL = "0x" + "44" * 20


class Registry:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""
            CREATE TABLE universe_pool_registry(
                dex TEXT NOT NULL,
                pool TEXT NOT NULL
            )
        """)
        self.db.executemany(
            "INSERT INTO universe_pool_registry(dex,pool) VALUES(?,?)",
            [
                ("pancakeswap_v2", V2_POOL),
                ("pancakeswap_v3", V3_POOL),
                ("uniswap_v3", UNI_POOL),
            ],
        )


def test_activity_radar_scans_topics_chain_wide_and_only_queues_pancake():
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        return [
            {"address": V2_POOL},
            {"address": V3_POOL},
            {"address": UNI_POOL},
            {"address": UNKNOWN_POOL},
        ]

    radar = PancakeActivityRadar(
        Registry(),
        reader,
        poll_seconds=5,
        replay_blocks=4,
        priority_batch=30,
        now_func=lambda: 100.0,
    )

    result = radar.run_once(finalized_block=1000)

    assert calls == [{
        "topics": PANCAKE_ACTIVITY_TOPICS,
        "from_block": 997,
        "to_block": 1000,
    }]
    assert set(result["priority_pools"]) == {V2_POOL, V3_POOL}
    assert result["matched_events"] == 2
    assert result["events"] == 4
    assert result["provider_call"] is True
    assert result["pending"] == 2
    assert result["unknown_pending"] == 2


def test_activity_radar_preserves_fifo_until_successful_acknowledgment():
    now = [100.0]

    def reader(**kwargs):
        return [{"address": V2_POOL}, {"address": V3_POOL}]

    radar = PancakeActivityRadar(
        Registry(),
        reader,
        poll_seconds=1,
        priority_batch=1,
        now_func=lambda: now[0],
    )

    first = radar.run_once(finalized_block=200)
    first_pool = first["priority_pools"][0]
    other_pool = V3_POOL if first_pool == V2_POOL else V2_POOL
    assert first_pool in {V2_POOL, V3_POOL}
    assert first["pending"] == 2

    now[0] = 102.0
    repeated = radar.run_once(finalized_block=201)
    assert repeated["priority_pools"] == [first_pool]
    assert repeated["pending"] == 2

    assert radar.acknowledge([first_pool]) == 1

    now[0] = 104.0
    next_result = radar.run_once(finalized_block=202)
    assert next_result["priority_pools"] == [other_pool]
    assert next_result["pending"] == 2


def test_activity_radar_persists_cursor_and_retries_failed_range():
    registry = Registry()
    now = [100.0]
    calls = []
    fail = [False]

    def reader(**kwargs):
        calls.append(kwargs)
        if fail[0]:
            raise ConnectionError("provider unavailable")
        return []

    first = PancakeActivityRadar(
        registry,
        reader,
        poll_seconds=1,
        replay_blocks=4,
        now_func=lambda: now[0],
    )
    result = first.run_once(finalized_block=1000)
    assert result["last_scanned_block"] == 1000

    restarted = PancakeActivityRadar(
        registry,
        reader,
        poll_seconds=1,
        replay_blocks=4,
        now_func=lambda: now[0],
    )
    now[0] = 102.0
    result = restarted.run_once(finalized_block=1002)
    assert calls[-1]["from_block"] == 1001
    assert calls[-1]["to_block"] == 1002
    assert result["last_scanned_block"] == 1002

    fail[0] = True
    now[0] = 104.0
    failed = restarted.run_once(finalized_block=1004)
    assert failed["state"] == "DEGRADED"
    assert failed["last_scanned_block"] == 1002

    fail[0] = False
    now[0] = 106.0
    retried = restarted.run_once(finalized_block=1004)
    assert calls[-1]["from_block"] == 1003
    assert calls[-1]["to_block"] == 1004
    assert retried["last_scanned_block"] == 1004


def test_pending_priority_work_survives_restart_until_acknowledged():
    registry = Registry()
    now = [100.0]

    first = PancakeActivityRadar(
        registry,
        lambda **_: [{"address": V2_POOL}],
        poll_seconds=1,
        priority_batch=1,
        now_func=lambda: now[0],
    )
    scanned = first.run_once(finalized_block=700)
    assert scanned["priority_pools"] == [V2_POOL]
    assert scanned["pending"] == 1

    restarted = PancakeActivityRadar(
        registry,
        lambda **_: [],
        poll_seconds=1,
        priority_batch=1,
        now_func=lambda: now[0],
    )
    now[0] = 102.0
    after_restart = restarted.run_once(finalized_block=700)
    assert after_restart["priority_pools"] == [V2_POOL]
    assert after_restart["pending"] == 1

    assert restarted.acknowledge([V2_POOL]) == 1
    now[0] = 104.0
    after_ack = restarted.run_once(finalized_block=700)
    assert after_ack["priority_pools"] == []
    assert after_ack["pending"] == 0


def test_unknown_swap_is_promoted_after_factory_discovery_and_survives_restart():
    registry = Registry()
    now = [100.0]

    radar = PancakeActivityRadar(
        registry,
        lambda **_: [{"address": UNKNOWN_POOL}],
        poll_seconds=5,
        priority_batch=30,
        now_func=lambda: now[0],
    )

    first = radar.run_once(finalized_block=500)
    assert first["priority_pools"] == []
    assert first["unknown_pending"] == 1

    restarted = PancakeActivityRadar(
        registry,
        lambda **_: [],
        poll_seconds=5,
        priority_batch=30,
        now_func=lambda: now[0],
    )
    registry.db.execute(
        "INSERT INTO universe_pool_registry(dex,pool) VALUES(?,?)",
        ("pancakeswap_v2", UNKNOWN_POOL),
    )
    registry.db.commit()

    now[0] = 101.0
    second = restarted.run_once(finalized_block=500)
    assert second["provider_call"] is False
    assert second["promoted_after_discovery"] == 1
    assert second["priority_pools"] == [UNKNOWN_POOL]
    assert second["unknown_pending"] == 0


def test_web3_topic_reader_uses_no_address_filter():
    captured = []

    class Eth:
        def get_logs(self, payload):
            captured.append(payload)
            return []

    class Web3:
        eth = Eth()

    reader = Web3TopicLogReader(Web3())
    assert reader(
        topics=PANCAKE_ACTIVITY_TOPICS,
        from_block=10,
        to_block=20,
    ) == []

    assert captured == [{
        "topics": [list(PANCAKE_ACTIVITY_TOPICS)],
        "fromBlock": 10,
        "toBlock": 20,
    }]
    assert "address" not in captured[0]
    assert PANCAKE_V3_SWAP_TOPIC in captured[0]["topics"][0]
