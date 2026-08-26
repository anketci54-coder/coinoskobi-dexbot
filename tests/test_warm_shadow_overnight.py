import importlib.util
from datetime import datetime
from pathlib import Path


MODULE_PATH = Path("scripts/warm_shadow_overnight.py")


def load_module():
    spec = importlib.util.spec_from_file_location(
        "warm_shadow_overnight", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_warm_shadow_contract_and_math(tmp_path):
    module = load_module()

    assert module.WINDOWS == (15, 30, 60, 120)
    assert module.MAX_ACTIVE_V2 == 16
    assert module.MAX_ACTOR_EVENTS_PER_POOL == 64
    assert module.pct(100, 110) == 10.000000000000009
    assert module.pct(None, 110) is None

    recorder = module.Recorder(tmp_path / "shadow.db")
    recorder.set_meta("authority", "OBSERVATION_ONLY")
    recorder.set_meta("last_eval_id", 123)

    assert recorder.get_meta_int("last_eval_id") == 123
    assert recorder.db.execute(
        "SELECT value FROM meta WHERE key='authority'"
    ).fetchone()[0] == "OBSERVATION_ONLY"

    tables = {
        row[0]
        for row in recorder.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"episodes", "windows", "native_events", "meta"}.issubset(tables)

    recorder.db.close()


def test_windows_are_anchored_to_trigger_time_and_ignore_enrichment(tmp_path):
    module = load_module()
    recorder = module.Recorder(tmp_path / "shadow.db")
    triggered_at = "2026-08-26T20:00:00+00:00"
    trigger_epoch = datetime.fromisoformat(triggered_at).timestamp()

    episode_id = recorder.add_episode({
        "eval_id": 1,
        "chain": "bsc",
        "dex": "pancakeswap_v2",
        "pool": "0x0000000000000000000000000000000000000001",
        "token": "0x0000000000000000000000000000000000000002",
        "quote_token": "0x0000000000000000000000000000000000000003",
        "previous_state": "COLD",
        "trigger_state": "WARM",
        "triggered_at": triggered_at,
        "trigger_price": 1.0,
        "trigger_liquidity": 1000.0,
        "trigger_volume_m5": 100.0,
        "trigger_txns_m5": 10,
        "price_z": 3.1,
        "volume_z": 4.0,
        "txns_z": 2.0,
        "liquidity_ratio": 1.0,
        "membership_state": "PENDING",
        "sellability": None,
        "stream_calibration": {"state": "READY"},
        "tracking_state": "ENRICHING",
    })

    rows = recorder.db.execute(
        "SELECT window_seconds,due_at_epoch FROM windows "
        "WHERE episode_id=? ORDER BY window_seconds",
        (episode_id,),
    ).fetchall()
    assert [row[0] for row in rows] == [15, 30, 60, 120]
    assert [row[1] for row in rows] == [
        trigger_epoch + 15,
        trigger_epoch + 30,
        trigger_epoch + 60,
        trigger_epoch + 120,
    ]

    due = recorder.due_windows(trigger_epoch + 15.1)
    assert len(due) == 1
    assert due[0]["window_seconds"] == 15

    recorder.update_enrichment(
        episode_id,
        membership_state="FACTORY_MISMATCH",
        sellability={"success": False},
        tracking_state="MEMBERSHIP_NOT_VERIFIED",
    )
    due_after_reject = recorder.due_windows(trigger_epoch + 30.1)
    assert {row["window_seconds"] for row in due_after_reject} == {15, 30}

    recorder.db.close()


def test_shadow_has_no_trade_authority():
    text = MODULE_PATH.read_text()
    assert "PAPER_BUY" not in text
    assert "PRIVATE_KEY" not in text
    assert "execution_authority" not in text.lower()
    assert "AUTHORITY=OBSERVATION_ONLY" in text
    assert "ThreadPoolExecutor" in text
