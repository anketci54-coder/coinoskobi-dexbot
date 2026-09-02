import sqlite3

import app.learning.watch_probe_store as watch_probe_store_module
from app.learning.watch_probe_store import WatchProbeStore


def test_watch_probe_opens_exactly_one_usdt(tmp_path):
    db = tmp_path / "paper.db"
    store = WatchProbeStore(db)

    result = store.open_probe(
        token="0xABC",
        pool="0xDEF",
        entry_price=0.25,
        opened_at=1000.0,
        decision_history_id=123,
    )

    assert result["state"] == "OPENED"
    assert result["created"] is True
    assert result["entry_usdt"] == 1.0
    assert result["token_amount"] == 4.0

    row = sqlite3.connect(db).execute(
        """
        SELECT
            token,
            pool,
            entry_price,
            entry_usdt,
            token_amount,
            status,
            decision_history_id
        FROM watch_probe_trades
        """
    ).fetchone()

    assert row == (
        "0xabc",
        "0xdef",
        0.25,
        1.0,
        4.0,
        "OPEN",
        123,
    )


def test_watch_probe_is_unique_per_token_pool(tmp_path):
    store = WatchProbeStore(tmp_path / "paper.db")

    first = store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=2.0,
    )

    second = store.open_probe(
        token="0xABC",
        pool="0xDEF",
        entry_price=3.0,
    )

    assert first["created"] is True
    assert second["created"] is False
    assert second["state"] == "ALREADY_EXISTS"


def test_watch_probe_observation_updates_price_extremes(tmp_path):
    store = WatchProbeStore(tmp_path / "paper.db")

    store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=1.0,
        opened_at=1000.0,
    )

    result = store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=1.5,
        observed_at=1010.0,
    )

    assert result == {
        "state": "OBSERVED",
        "updated": 1,
        "exit_candidates": 0,
        "exit_attempted": 0,
        "exit_verified": 0,
        "exit_deferred": 0,
    }

    row = store.snapshot(1)[0]

    assert row["last_price"] == 1.5
    assert row["max_price"] == 1.5
    assert row["min_price"] == 1.0
    assert row["entry_usdt"] == 1.0
    assert row["status"] == "OPEN"


def test_watch_probe_v2_schema_is_additive_and_metrics_update(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"

    monkeypatch.setattr(
        watch_probe_store_module,
        "probe_watch_exit",
        lambda **kwargs: {
            "state": "DEFERRED",
            "attempted": False,
            "quality": "BOUNDED",
            "reason": "TEST",
            "realizable_exit_usdt": None,
        },
    )

    store = WatchProbeStore(db)

    store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=1.0,
        opened_at=1000.0,
    )

    store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=2.0,
        observed_at=1010.0,
    )

    store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=1.5,
        observed_at=1020.0,
    )

    row = store.snapshot(1)[0]

    assert row["mark_return_pct"] == 50.0
    assert row["mfe_pct"] == 100.0
    assert row["mae_pct"] == 0.0
    assert row["peak_drawdown_pct"] == -25.0

    assert row["realizable_exit_usdt"] is None
    assert row["realizable_return_pct"] is None
    assert row["exit_state"] == "UNVERIFIED"
    assert row["closed_at"] is None


def test_watch_probe_v2_migrates_existing_table_without_data_loss(tmp_path):
    db = tmp_path / "paper.db"

    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE watch_probe_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            pool TEXT NOT NULL,
            opened_at REAL NOT NULL,
            entry_price REAL NOT NULL,
            entry_usdt REAL NOT NULL DEFAULT 1.0,
            token_amount REAL NOT NULL,
            last_observed_at REAL,
            last_price REAL,
            max_price REAL,
            min_price REAL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            decision_history_id INTEGER,
            UNIQUE(token, pool)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO watch_probe_trades(
            token,
            pool,
            opened_at,
            entry_price,
            entry_usdt,
            token_amount,
            last_observed_at,
            last_price,
            max_price,
            min_price,
            status
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "0xabc",
            "0xdef",
            1000.0,
            1.0,
            1.0,
            1.0,
            1000.0,
            1.0,
            1.0,
            1.0,
            "OPEN",
        ),
    )
    conn.commit()
    conn.close()

    store = WatchProbeStore(db)

    row = store.snapshot(1)[0]

    assert row["token"] == "0xabc"
    assert row["entry_usdt"] == 1.0
    assert row["exit_state"] == "UNVERIFIED"

    columns = {
        r[1]
        for r in sqlite3.connect(db).execute(
            "PRAGMA table_info(watch_probe_trades)"
        )
    }

    assert "mfe_pct" in columns
    assert "mae_pct" in columns
    assert "realizable_exit_usdt" in columns
    assert "exit_state" in columns


def test_watch_probe_shadow_exit_tp_and_trailing(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    monkeypatch.setattr(
        watch_probe_store_module,
        "probe_watch_exit",
        lambda **kwargs: {
            "state": "DEFERRED",
            "attempted": False,
            "quality": "BOUNDED",
            "reason": "TEST",
            "realizable_exit_usdt": None,
        },
    )
    store = WatchProbeStore(db)

    store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=1.0,
        opened_at=1000.0,
    )

    store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=2.1,
        observed_at=1100.0,
    )

    store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=1.5,
        observed_at=1200.0,
    )

    rows = store._db.execute(
        """
        SELECT strategy, state, reason, return_pct
        FROM watch_probe_shadow_exits
        ORDER BY strategy
        """
    ).fetchall()

    data = {r["strategy"]: dict(r) for r in rows}

    assert data["TP_2X"]["state"] == "TRIGGERED"
    assert data["TP_2X"]["reason"] == "TARGET_2X"

    assert data["TRAIL_25"]["state"] == "TRIGGERED"
    assert data["TRAIL_25"]["reason"] == "PEAK_DRAWDOWN_25"

    assert data["TP_5X"]["state"] == "ARMED"


def test_watch_probe_shadow_exit_time_rules(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    monkeypatch.setattr(
        watch_probe_store_module,
        "probe_watch_exit",
        lambda **kwargs: {
            "state": "DEFERRED",
            "attempted": False,
            "quality": "BOUNDED",
            "reason": "TEST",
            "realizable_exit_usdt": None,
        },
    )
    store = WatchProbeStore(db)

    store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=1.0,
        opened_at=1000.0,
    )

    store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=1.2,
        observed_at=4700.0,
    )

    row = store._db.execute(
        """
        SELECT state, reason
        FROM watch_probe_shadow_exits
        WHERE strategy='TIME_60M'
        """
    ).fetchone()

    assert row["state"] == "TRIGGERED"
    assert row["reason"] == "TIME_60M"

    row = store._db.execute(
        """
        SELECT state
        FROM watch_probe_shadow_exits
        WHERE strategy='TIME_6H'
        """
    ).fetchone()

    assert row["state"] == "ARMED"


def test_triggered_watch_probe_verified_exit_closes_same_row(tmp_path, monkeypatch):
    store = WatchProbeStore(tmp_path / "paper.db")
    store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=1.0,
        opened_at=1000.0,
    )

    calls = []

    def fake_probe(**kwargs):
        calls.append(kwargs)
        return {
            "state": "VERIFIED",
            "attempted": True,
            "quality": "SELLABILITY_PLUS_EXACT_ROUTE_QUOTE",
            "reason": "SIMULATED_EXIT_VERIFIED",
            "realizable_exit_usdt": 1.8,
        }

    monkeypatch.setattr(
        watch_probe_store_module,
        "probe_watch_exit",
        fake_probe,
    )

    result = store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=2.0,
        observed_at=1100.0,
    )

    assert len(calls) == 1
    assert result["exit_candidates"] == 1
    assert result["exit_attempted"] == 1
    assert result["exit_verified"] == 1

    row = store.snapshot(1)[0]
    assert row["status"] == "CLOSED"
    assert row["exit_state"] == "VERIFIED"
    assert row["realizable_exit_usdt"] == 1.8
    assert row["realizable_return_pct"] == 80.0
    assert row["closed_at"] == 1100.0
    assert row["last_exit_probe_at"] == 1100.0
    assert row["context_version"] == "WATCH_PROBE_EXIT_V1"


def test_triggered_watch_probe_unverified_stays_open_and_retries_bounded(tmp_path, monkeypatch):
    store = WatchProbeStore(tmp_path / "paper.db")
    store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=1.0,
        opened_at=1000.0,
    )

    calls = []

    def fake_probe(**kwargs):
        calls.append(kwargs)
        return {
            "state": "UNVERIFIED",
            "attempted": True,
            "quality": "PROVIDER_ERROR",
            "reason": "SELLABILITY_PROBE_FAILED",
            "realizable_exit_usdt": None,
        }

    monkeypatch.setattr(
        watch_probe_store_module,
        "probe_watch_exit",
        fake_probe,
    )

    first = store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=2.0,
        observed_at=1100.0,
    )
    second = store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=1.9,
        observed_at=1200.0,
    )
    third = store.observe(
        token="0xabc",
        pool="0xdef",
        current_price=1.8,
        observed_at=2101.0,
    )

    assert first["exit_attempted"] == 1
    assert second["exit_candidates"] == 0
    assert third["exit_attempted"] == 1
    assert len(calls) == 2

    row = store.snapshot(1)[0]
    assert row["status"] == "OPEN"
    assert row["exit_state"] == "UNVERIFIED"
    assert row["realizable_exit_usdt"] is None
    assert row["last_exit_probe_at"] == 2101.0


def test_watch_probe_observation_is_exact_pool_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(
        watch_probe_store_module,
        "probe_watch_exit",
        lambda **kwargs: {
            "state": "DEFERRED",
            "attempted": False,
            "quality": "BOUNDED",
            "reason": "TEST",
            "realizable_exit_usdt": None,
        },
    )
    store = WatchProbeStore(tmp_path / "paper.db")

    store.open_probe(
        token="0xabc",
        pool="0xpool1",
        entry_price=1.0,
        opened_at=1000.0,
    )

    store.open_probe(
        token="0xabc",
        pool="0xpool2",
        entry_price=10.0,
        opened_at=1000.0,
    )

    result = store.observe(
        token="0xabc",
        pool="0xpool1",
        current_price=2.0,
        observed_at=1100.0,
    )

    assert result["updated"] == 1

    rows = {
        r["pool"]: r
        for r in store.snapshot(10)
    }

    assert rows["0xpool1"]["last_price"] == 2.0
    assert rows["0xpool1"]["mark_return_pct"] == 100.0

    assert rows["0xpool2"]["last_price"] == 10.0
    assert rows["0xpool2"]["mark_return_pct"] is None


def test_watch_probe_rejects_token_pool_collision(tmp_path):
    store = WatchProbeStore(tmp_path / "paper.db")

    address = "0x1111111111111111111111111111111111111111"

    result = store.open_probe(
        token=address,
        pool=address,
        entry_price=0.01,
    )

    assert result["state"] == "INVALID"
    assert result["created"] is False

    observed = store.observe(
        token=address,
        pool=address,
        current_price=0.02,
    )

    assert observed["state"] == "INVALID"
    assert observed["updated"] == 0
