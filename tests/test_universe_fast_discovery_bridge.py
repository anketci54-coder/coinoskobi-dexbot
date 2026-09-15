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
