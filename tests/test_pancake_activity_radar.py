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


def test_unknown_queue_evicts_oldest_so_new_factory_races_can_enter():
    registry = Registry()
    now = [100.0]
    addresses = ["0x" + value * 40 for value in ("5", "6", "7")]
    current = [addresses[0]]

    radar = PancakeActivityRadar(
        registry,
        lambda **_: [{"address": current[0]}],
        poll_seconds=1,
        priority_batch=1,
        max_pending=2,
        now_func=lambda: now[0],
    )

    radar.run_once(finalized_block=800)
    current[0] = addresses[1]
    now[0] = 102.0
    radar.run_once(finalized_block=801)
    current[0] = addresses[2]
    now[0] = 104.0
    result = radar.run_once(finalized_block=802)

    rows = registry.db.execute("""
        SELECT pool FROM universe_activity_pending_v1
        WHERE kind='UNKNOWN' ORDER BY seq
    """).fetchall()
    assert [row[0] for row in rows] == addresses[1:]
    assert result["unknown_pending"] == 2
    assert result["dropped_unknown"] == 1


def test_full_known_queue_retains_new_activity_until_capacity_opens():
    registry = Registry()
    now = [100.0]
    current = [V2_POOL]

    radar = PancakeActivityRadar(
        registry,
        lambda **_: [{"address": current[0]}],
        poll_seconds=1,
        priority_batch=1,
        max_pending=1,
        now_func=lambda: now[0],
    )

    first = radar.run_once(finalized_block=900)
    assert first["priority_pools"] == [V2_POOL]
    assert first["pending"] == 1

    current[0] = V3_POOL
    now[0] = 102.0
    second = radar.run_once(finalized_block=901)
    assert second["priority_pools"] == [V2_POOL]
    assert second["pending"] == 1
    assert second["unknown_pending"] == 1

    assert radar.acknowledge([V2_POOL]) == 1
    now[0] = 104.0
    third = radar.run_once(finalized_block=901)
    assert third["provider_call"] is False
    assert third["promoted_after_discovery"] == 1
    assert third["priority_pools"] == [V3_POOL]
    assert third["unknown_pending"] == 0


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


def test_same_scan_known_admission_preserves_chain_log_order():
    registry = Registry()
    now = [100.0]

    radar = PancakeActivityRadar(
        registry,
        lambda **_: [
            {"address": V2_POOL},
            {"address": V3_POOL},
        ],
        poll_seconds=1,
        priority_batch=1,
        max_pending=1,
        now_func=lambda: now[0],
    )

    result = radar.run_once(finalized_block=950)

    assert result["priority_pools"] == [V2_POOL]
    assert result["pending"] == 1
    assert result["unknown_pending"] == 1


def test_registered_overflow_survives_unknown_eviction_pressure():
    registry = Registry()
    now = [100.0]
    current = [[{"address": V2_POOL}]]

    radar = PancakeActivityRadar(
        registry,
        lambda **_: current[0],
        poll_seconds=1,
        priority_batch=1,
        max_pending=1,
        now_func=lambda: now[0],
    )

    first = radar.run_once(finalized_block=960)
    assert first["priority_pools"] == [V2_POOL]

    current[0] = [{"address": V3_POOL}]
    now[0] = 102.0
    second = radar.run_once(finalized_block=961)

    assert second["priority_pools"] == [V2_POOL]
    assert second["unknown_pending"] == 1

    fork_a = "0x" + "55" * 20
    fork_b = "0x" + "66" * 20
    current[0] = [
        {"address": fork_a},
        {"address": fork_b},
    ]
    now[0] = 104.0
    radar.run_once(finalized_block=962)

    rows = registry.db.execute("""
        SELECT pool
        FROM universe_activity_pending_v1
        WHERE kind='UNKNOWN'
    """).fetchall()

    assert (V3_POOL,) in rows

    assert radar.acknowledge([V2_POOL]) == 1

    current[0] = []
    now[0] = 106.0
    promoted = radar.run_once(finalized_block=962)

    assert promoted["priority_pools"] == [V3_POOL]


def _production_radar(tmp_path):
    from app.universe.registry import UniverseRegistry

    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.db.execute("PRAGMA journal_mode=WAL")
    registry.ingest([
        {
            "dex": "pancakeswap_v2", "pool": f"0x{i:040x}",
            "factory": V2_POOL, "creation_block": i,
            "discovery_branch": "EXISTING",
        }
        for i in range(1, 2001)
    ])
    radar = PancakeActivityRadar(
        registry, lambda **_: [], priority_batch=1, max_pending=100,
    )
    return registry, radar


def test_activity_trim_bounds_work_inside_cache_write_transaction(tmp_path):
    registry, radar = _production_radar(tmp_path)
    statements = []
    registry.db.set_trace_callback(statements.append)
    # A VM instruction budget catches the nested full-DEX scans without a
    # timing-dependent assertion or a production-sized database.
    registry.db.set_progress_handler(lambda: 1, 200000)
    try:
        radar._persist_scan(
            to_block=100,
            known=[],
            unknown=[f"0x{i:040x}" for i in range(3000, 3200)],
        )
        assert not registry.db.in_transaction
        assert len(radar._unknown_pending) == 100
        assert next(iter(radar._unknown_pending)) == f"0x{3100:040x}"
        trim = next(s for s in statements if "LEFT JOIN universe_pool_registry" in s)
        plan = registry.db.execute("EXPLAIN QUERY PLAN " + trim).fetchall()
        assert any("idx_universe_pool_dex" in row[3] for row in plan)
    finally:
        registry.db.set_progress_handler(None, 0)
        registry.close()


def test_activity_failed_scan_releases_writer_and_recovers(tmp_path, monkeypatch):
    import pytest
    from app.cache import gecko_cache

    registry, radar = _production_radar(tmp_path)
    monkeypatch.setattr(gecko_cache, "DB", tmp_path / "cache.db")
    cache = gecko_cache.GeckoCache()
    registry.db.execute("""
        CREATE TRIGGER fail_activity_cursor BEFORE INSERT
        ON universe_activity_cursor_v1
        BEGIN SELECT RAISE(ABORT, 'cursor failure'); END
    """)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="cursor failure"):
            radar._persist_scan(to_block=100, known=[V2_POOL], unknown=[])
        assert not registry.db.in_transaction
        assert radar._last_scanned_block is None
        assert registry.db.execute(
            "SELECT COUNT(*) FROM universe_activity_pending_v1"
        ).fetchone()[0] == 0
        # Independent canonical cache connection must be immediately writable.
        cache.upsert_tracked_price(V2_POOL, V3_POOL, 1.0)
        registry.db.execute("DROP TRIGGER fail_activity_cursor")
        radar._persist_scan(to_block=101, known=[V2_POOL], unknown=[])
        assert radar._last_scanned_block == 101
        assert not registry.db.in_transaction
        cache.upsert_tracked_price(V2_POOL, V3_POOL, 2.0)
        assert cache.all()[0]["price_usd"] == 2.0
    finally:
        cache.db.close()
        registry.close()
