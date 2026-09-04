import sqlite3

import app.learning.watch_probe_sweeper as module
from app.learning.watch_probe_store import WatchProbeStore


def _open(store, token, pool, opened_at=1000.0):
    return store.open_probe(
        token=token,
        pool=pool,
        entry_price=1.0,
        opened_at=opened_at,
    )


def test_sweeper_time_trigger_verifies_stale_open_probe(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    store = WatchProbeStore(db)
    _open(store, "0xabc", "0xdef")

    calls = []

    def verify(**kwargs):
        calls.append(kwargs)
        return {
            "state": "VERIFIED",
            "attempted": True,
            "quality": "TEST",
            "reason": "SIMULATED_EXIT_VERIFIED",
            "realizable_exit_usdt": 1.25,
        }

    monkeypatch.setattr(module, "probe_watch_exit", verify)

    result = module.sweep_watch_probe_exits(
        db,
        now=5000.0,
    )

    assert result["state"] == "READY"
    assert result["selected"] == 1
    assert result["attempted"] == 1
    assert result["verified"] == 1
    assert len(calls) == 1

    row = sqlite3.connect(db).execute(
        """
        SELECT status, exit_state, realizable_exit_usdt,
               realizable_return_pct, closed_at
        FROM watch_probe_trades
        """
    ).fetchone()

    assert row[0] == "CLOSED"
    assert row[1] == "VERIFIED"
    assert row[2] == 1.25
    assert row[3] == 25.0
    assert row[4] == 5000.0

    trigger = sqlite3.connect(db).execute(
        """
        SELECT state, reason
        FROM watch_probe_shadow_exits
        WHERE strategy='TIME_60M'
        """
    ).fetchone()

    assert trigger == ("TRIGGERED", "TIME_60M")


def test_sweeper_respects_retry_window(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    store = WatchProbeStore(db)
    _open(store, "0xabc", "0xdef")

    store._db.execute(
        """
        UPDATE watch_probe_trades
        SET last_exit_probe_at=4900.0,
            exit_state='UNVERIFIED'
        """
    )
    store._db.commit()

    calls = []
    monkeypatch.setattr(
        module,
        "probe_watch_exit",
        lambda **kwargs: calls.append(kwargs),
    )

    result = module.sweep_watch_probe_exits(
        db,
        now=5000.0,
    )

    assert result["selected"] == 0
    assert calls == []


def test_sweeper_is_bounded_to_global_provider_budget(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    store = WatchProbeStore(db)

    for i in range(10):
        _open(
            store,
            f"0xtoken{i}",
            f"0xpool{i}",
        )

    calls = []

    def deferred(**kwargs):
        calls.append(kwargs)
        return {
            "state": "DEFERRED",
            "attempted": False,
            "quality": "BOUNDED",
            "reason": "TEST",
            "realizable_exit_usdt": None,
        }

    monkeypatch.setattr(module, "probe_watch_exit", deferred)

    result = module.sweep_watch_probe_exits(
        db,
        now=5000.0,
        max_entries=100,
    )

    assert result["selected"] == module.MAX_PROBES_PER_MINUTE
    assert result["max_entries"] == module.MAX_PROBES_PER_MINUTE
    assert len(calls) == module.MAX_PROBES_PER_MINUTE
    assert result["deferred"] == module.MAX_PROBES_PER_MINUTE


def test_sweeper_has_zero_trade_authority(tmp_path, monkeypatch):
    db = tmp_path / "paper.db"
    store = WatchProbeStore(db)
    _open(store, "0xabc", "0xdef")

    monkeypatch.setattr(
        module,
        "probe_watch_exit",
        lambda **kwargs: {
            "state": "DEFERRED",
            "attempted": False,
            "quality": "BOUNDED",
            "reason": "TEST",
            "realizable_exit_usdt": None,
        },
    )

    result = module.sweep_watch_probe_exits(db, now=5000.0)

    assert result["trade_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
