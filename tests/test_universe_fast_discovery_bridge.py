import sqlite3
import threading

import app.pipeline.fast_watch_revisit as module
from app.pipeline.fast_watch_revisit import FastWatchRevisitJob


def address(value):
    return "0x" + f"{value:040x}"


class DecisionStore:
    def __init__(self):
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._db.execute("""
            CREATE TABLE candidate_decision_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT,
                pool TEXT
            )
        """)


class Pipeline:
    def __init__(self):
        self.counterfactual_store = DecisionStore()


def make_universe(path, *, tail_block=2000):
    db = sqlite3.connect(path)
    db.execute("""
        CREATE TABLE universe_pool_registry(
            chain TEXT,
            dex TEXT,
            pool TEXT,
            token0 TEXT,
            token1 TEXT,
            creation_block INTEGER,
            discovery_branch TEXT
        )
    """)
    db.execute("""
        CREATE TABLE universe_discovery_checkpoint(
            chain TEXT,
            dex TEXT,
            factory TEXT,
            event_kind TEXT,
            discovery_branch TEXT,
            last_scanned_block INTEGER,
            last_finalized_block INTEGER,
            updated_at TEXT
        )
    """)
    db.execute(
        """
        INSERT INTO universe_discovery_checkpoint(
            chain, dex, factory, event_kind,
            discovery_branch, last_scanned_block,
            last_finalized_block, updated_at
        )
        VALUES(
            'bsc', ?, '0x0000000000000000000000000000000000000001',
            'PAIR_CREATED', 'NEW', ?, ?, 'now'
        )
        """,
        (
            module.DEX_PANCAKESWAP_V2,
            tail_block,
            tail_block,
        ),
    )
    db.commit()
    return db


def test_new_factory_pool_enters_fast_discovery_once(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    universe = make_universe(db_path, tail_block=100)

    base = next(iter(module.BASE_TOKEN_SET))
    token_old = address(1001)
    token_seen = address(1002)
    token_new = address(1003)

    pool_old = address(2001)
    pool_seen = address(2002)
    pool_new = address(2003)

    universe.executemany(
        """
        INSERT INTO universe_pool_registry(
            chain, dex, pool, token0, token1,
            creation_block, discovery_branch
        )
        VALUES('bsc', ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                module.DEX_PANCAKESWAP_V2,
                pool_old,
                base,
                token_old,
                10,
                "EXISTING",
            ),
            (
                module.DEX_PANCAKESWAP_V2,
                pool_seen,
                base,
                token_seen,
                20,
                "NEW",
            ),
            (
                module.DEX_PANCAKESWAP_V2,
                pool_new,
                base,
                token_new,
                30,
                "EXISTING",
            ),
        ],
    )
    universe.commit()
    universe.close()

    pipeline = Pipeline()
    pipeline.counterfactual_store._db.execute(
        """
        INSERT INTO candidate_decision_history(token, pool)
        VALUES(?, ?)
        """,
        (token_seen, pool_seen),
    )
    pipeline.counterfactual_store._db.commit()

    monkeypatch.setattr(module, "DEFAULT_DB", db_path)

    job = FastWatchRevisitJob(pipeline)

    assert job._unseen_universe_identities() == [
        (
            token_new,
            pool_new,
            module.DEX_PANCAKESWAP_V2,
        ),
        (
            token_old,
            pool_old,
            module.DEX_PANCAKESWAP_V2,
        ),
    ]


def test_fast_cycle_processes_discovery_without_existing_watch(monkeypatch):
    pipeline = Pipeline()
    job = FastWatchRevisitJob(pipeline)

    token = address(3001)
    pool = address(3002)

    monkeypatch.setattr(
        job,
        "_unseen_universe_identities",
        lambda: [(token, pool)],
    )
    monkeypatch.setattr(
        job,
        "_watched_identities",
        lambda: [],
    )
    monkeypatch.setattr(
        job,
        "_fresh_rows",
        lambda identities: [{
            "token": token,
            "pool": pool,
            "quote_token": address(3003),
        }],
    )
    monkeypatch.setattr(
        job,
        "_refresh_local_sellability_evidence",
        lambda row: True,
    )
    monkeypatch.setattr(
        job,
        "_process",
        lambda row: {
            "data": {
                "paper": {
                    "action": "WATCH",
                }
            }
        },
    )

    result = job._run_cycle_sync()

    assert result["state"] == "READY"
    assert result["selected"] == 1
    assert result["processed"] == 1
    assert result["failed"] == 0
    assert result["paper_buys"] == 0


def test_fast_discovery_is_bounded(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    universe = make_universe(db_path, tail_block=2000)

    base = next(iter(module.BASE_TOKEN_SET))

    for i in range(module.FAST_DISCOVERY_MAX_CANDIDATES + 20):
        universe.execute(
            """
            INSERT INTO universe_pool_registry(
                chain, dex, pool, token0, token1,
                creation_block, discovery_branch
            )
            VALUES('bsc', ?, ?, ?, ?, ?, 'NEW')
            """,
            (
                module.DEX_PANCAKESWAP_V2,
                address(5000 + i),
                base,
                address(6000 + i),
                1000 + i,
            ),
        )

    universe.commit()
    universe.close()

    monkeypatch.setattr(module, "DEFAULT_DB", db_path)

    job = FastWatchRevisitJob(Pipeline())
    rows = job._unseen_universe_identities()

    assert len(rows) == module.FAST_DISCOVERY_MAX_CANDIDATES


def test_fast_discovery_cooldown_rotates_unseen_pool_batch(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cache.db"
    universe = make_universe(db_path, tail_block=3000)

    base = next(iter(module.BASE_TOKEN_SET))

    for i in range(module.FAST_DISCOVERY_MAX_CANDIDATES + 2):
        universe.execute(
            """
            INSERT INTO universe_pool_registry(
                chain, dex, pool, token0, token1,
                creation_block, discovery_branch
            )
            VALUES('bsc', ?, ?, ?, ?, ?, 'EXISTING')
            """,
            (
                module.DEX_PANCAKESWAP_V2,
                address(7000 + i),
                base,
                address(8000 + i),
                2900 + i,
            ),
        )

    universe.commit()
    universe.close()

    monkeypatch.setattr(module, "DEFAULT_DB", db_path)

    job = FastWatchRevisitJob(Pipeline())

    first = job._unseen_universe_identities()
    second = job._unseen_universe_identities()

    assert len(first) == module.FAST_DISCOVERY_MAX_CANDIDATES
    assert len(second) == 2
    assert set(first).isdisjoint(second)


def test_hot_universe_bridge_is_bounded_v2_only_and_worker_thread_safe(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "cache.db"
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE universe_pool_registry(
            chain TEXT,
            dex TEXT,
            pool TEXT,
            token0 TEXT,
            token1 TEXT,
            creation_block INTEGER,
            market_state TEXT,
            latest_snapshot_at TEXT,
            latest_price_usd REAL,
            latest_liquidity_usd REAL,
            latest_volume_24h REAL,
            latest_snapshot_source TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE universe_seismic_evaluation_v1(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain TEXT,
            dex TEXT,
            pool TEXT,
            observed_at TEXT,
            score REAL
        )
        """
    )

    base = next(iter(module.BASE_TOKEN_SET))

    for i in range(module.FAST_HOT_UNIVERSE_MAX_CANDIDATES + 5):
        pool = address(10000 + i)
        db.execute(
            """
            INSERT INTO universe_pool_registry(
                chain, dex, pool, token0, token1, creation_block,
                market_state, latest_snapshot_at
            )
            VALUES('bsc', ?, ?, ?, ?, ?, 'HOT', ?)
            """,
            (
                module.DEX_PANCAKESWAP_V2,
                pool,
                base,
                address(9000 + i),
                20000 + i,
                f"2026-09-20T00:00:{i:02d}+00:00",
            ),
        )
        db.execute(
            """
            INSERT INTO universe_seismic_evaluation_v1(
                chain, dex, pool, observed_at, score
            )
            VALUES('bsc', ?, ?, ?, ?)
            """,
            (
                module.DEX_PANCAKESWAP_V2,
                pool,
                f"2026-09-20T00:00:{i:02d}+00:00",
                100 - i,
            ),
        )

    db.execute(
        """
        INSERT INTO universe_pool_registry(
            chain, dex, pool, token0, token1, creation_block,
            market_state, latest_snapshot_at
        )
        VALUES('bsc', 'pancakeswap_v3', ?, ?, ?, 30000, 'HOT', 'now')
        """,
        (address(12002), base, address(12001)),
    )
    db.execute(
        """
        INSERT INTO universe_pool_registry(
            chain, dex, pool, token0, token1, creation_block,
            market_state, latest_snapshot_at
        )
        VALUES('bsc', ?, ?, ?, ?, 30001, 'WARM', 'now')
        """,
        (
            module.DEX_PANCAKESWAP_V2,
            address(12004),
            base,
            address(12003),
        ),
    )
    db.commit()
    db.close()

    monkeypatch.setattr(module, "DEFAULT_DB", db_path)

    job = FastWatchRevisitJob(Pipeline())
    captured = {}

    def worker():
        captured["selected"] = job._hot_universe_identities()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive()
    selected = captured["selected"]
    assert (
        len(selected)
        == module.FAST_HOT_UNIVERSE_MAX_CANDIDATES
    )
    assert all(
        identity[2]
        == module.DEX_PANCAKESWAP_V2
        for identity in selected
    )


def test_fast_cycle_prioritizes_hot_universe_before_discovery_and_watch(
    monkeypatch,
):
    pipeline = Pipeline()
    job = FastWatchRevisitJob(pipeline)

    hot = (
        address(13001),
        address(13002),
        module.DEX_PANCAKESWAP_V2,
    )
    discovery = (
        address(13003),
        address(13004),
        module.DEX_PANCAKESWAP_V2,
    )
    watch = (
        address(13005),
        address(13006),
        module.DEX_PANCAKESWAP_V2,
    )

    monkeypatch.setattr(
        job,
        "_hot_universe_identities",
        lambda: [hot],
    )
    monkeypatch.setattr(
        job,
        "_unseen_universe_identities",
        lambda: [discovery],
    )
    monkeypatch.setattr(
        job,
        "_watched_identities",
        lambda: [watch],
    )

    captured = {}

    def fresh_rows(identities):
        captured["identities"] = list(identities)
        return [
            {
                "token": identity[0],
                "pool": identity[1],
                "quote_token": address(13999),
            }
            for identity in identities
        ]

    monkeypatch.setattr(
        job,
        "_fresh_rows",
        fresh_rows,
    )
    monkeypatch.setattr(
        job,
        "_refresh_local_sellability_evidence",
        lambda row: True,
    )
    monkeypatch.setattr(
        job,
        "_process",
        lambda row: {
            "data": {
                "paper": {
                    "action": "WATCH",
                }
            }
        },
    )

    result = job._run_cycle_sync()

    assert captured["identities"] == [
        hot,
        discovery,
        watch,
    ]
    assert result["state"] == "READY"
    assert result["selected"] == 3
    assert result["processed"] == 3
    assert result["failed"] == 0
