import sqlite3

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
        current_price=1.5,
        observed_at=1010.0,
    )

    assert result == {
        "state": "OBSERVED",
        "updated": 1,
    }

    row = store.snapshot(1)[0]

    assert row["last_price"] == 1.5
    assert row["max_price"] == 1.5
    assert row["min_price"] == 1.0
    assert row["entry_usdt"] == 1.0
    assert row["status"] == "OPEN"


def test_watch_probe_v2_schema_is_additive_and_metrics_update(tmp_path):
    db = tmp_path / "paper.db"

    store = WatchProbeStore(db)

    store.open_probe(
        token="0xabc",
        pool="0xdef",
        entry_price=1.0,
        opened_at=1000.0,
    )

    store.observe(
        token="0xabc",
        current_price=2.0,
        observed_at=1010.0,
    )

    store.observe(
        token="0xabc",
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
