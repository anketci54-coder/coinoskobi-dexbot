import importlib.util
from pathlib import Path


MODULE_PATH = Path("scripts/warm_shadow_prospective.py")


def load_module():
    spec = importlib.util.spec_from_file_location(
        "warm_shadow_prospective", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prospective_contract(tmp_path):
    module = load_module()

    assert module.COLLECTOR_VERSION == "WARM_PROSPECTIVE_EARLY_FLOW_V1"
    assert module.MEMBERSHIP_WORKERS == 4
    assert module.SELLABILITY_WORKERS == 2
    assert module.DEFAULT_POLL_SECONDS == 0.25

    recorder = module.ProspectiveRecorder(tmp_path / "prospective.db")

    columns = {
        row[1]
        for row in recorder.db.execute("PRAGMA table_info(episodes)").fetchall()
    }

    assert {
        "trigger_buys_m5",
        "trigger_sells_m5",
        "trigger_change_m5",
        "pretrigger_json",
        "membership_completed_at",
        "sellability_completed_at",
        "wss_eligible_at",
        "wss_requested_at",
        "first_native_at",
        "collector_version",
    }.issubset(columns)

    tables = {
        row[0]
        for row in recorder.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "collector_errors" in tables
    recorder.db.close()


def test_transient_window_failure_is_fail_soft(tmp_path):
    module = load_module()

    collector = object.__new__(module.ProspectiveCollector)
    collector.rec = module.ProspectiveRecorder(tmp_path / "prospective.db")

    original = module.BaseCollector.process_windows

    try:
        def broken(_self):
            raise ConnectionError("transient provider failure")

        module.BaseCollector.process_windows = broken
        assert collector.process_windows() == 0

        row = collector.rec.db.execute(
            "SELECT phase,error_class FROM collector_errors ORDER BY id DESC LIMIT 1"
        ).fetchone()

        assert row[0] == "SNAPSHOT_WINDOWS"
        assert row[1] == "ConnectionError"
    finally:
        module.BaseCollector.process_windows = original
        collector.rec.db.close()


def test_sellability_is_not_serially_blocked_by_membership():
    text = MODULE_PATH.read_text()

    assert "membership_future = self.enrichment_pool.submit(" in text
    assert "sellability_future = self.sellability_pool.submit(" in text
    assert text.index("membership_future = self.enrichment_pool.submit(") < text.index(
        "sellability_future = self.sellability_pool.submit("
    )
    assert "future = self.sellability_pool.submit(" not in text.split(
        "def _enrich_episode", 1
    )[1].split("def process_transitions", 1)[0]


def test_shutdown_waits_for_started_observation_workers():
    text = MODULE_PATH.read_text()

    close_body = text.split("def close(self):", 1)[1].split("def main():", 1)[0]
    assert "shutdown(wait=True, cancel_futures=False)" in close_body
    assert "shutdown(wait=False" not in close_body


def test_prospective_has_no_trade_authority():
    text = MODULE_PATH.read_text()
    assert "PAPER_BUY" not in text
    assert "PRIVATE_KEY" not in text
    assert "AUTHORITY=OBSERVATION_ONLY" in text
    assert "execution_authority" not in text.lower()
