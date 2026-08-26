import importlib.util
from pathlib import Path


MODULE_PATH = Path("scripts/warm_shadow_overnight.py")


def load_module():
    spec = importlib.util.spec_from_file_location("warm_shadow_overnight", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_warm_shadow_contract_and_math(tmp_path):
    module = load_module()

    assert module.WINDOWS == (15, 30, 60, 120)
    assert module.MAX_ACTIVE_V2 == 16
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


def test_shadow_has_no_trade_authority():
    text = MODULE_PATH.read_text()
    assert "PAPER_BUY" not in text
    assert "PRIVATE_KEY" not in text
    assert "execution_authority" not in text.lower()
    assert "AUTHORITY=OBSERVATION_ONLY" in text
