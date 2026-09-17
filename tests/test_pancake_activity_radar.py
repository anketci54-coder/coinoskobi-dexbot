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


def test_activity_radar_throttles_provider_but_can_drain_pending():
    now = [100.0]

    def reader(**kwargs):
        return [{"address": V2_POOL}, {"address": V3_POOL}]

    radar = PancakeActivityRadar(
        Registry(),
        reader,
        poll_seconds=5,
        priority_batch=1,
        now_func=lambda: now[0],
    )

    first = radar.run_once(finalized_block=200)
    assert first["provider_call"] is True
    assert first["priority_count"] == 1
    assert first["pending"] == 1

    now[0] = 101.0
    second = radar.run_once(finalized_block=201)
    assert second["state"] == "THROTTLED"
    assert second["provider_call"] is False
    assert second["priority_count"] == 1
    assert second["pending"] == 0


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
