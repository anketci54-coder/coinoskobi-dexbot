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
