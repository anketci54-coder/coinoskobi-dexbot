import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from app.core.runner import Runner


def test_sigterm_while_main_thread_owns_service_lock_exits_cleanly():
    # A real signal used to re-enter request_stop while its non-reentrant
    # lock was owned by the interrupted main thread, deadlocking shutdown.
    result = subprocess.run([sys.executable, "-c", '''
import os, signal, threading
from app.core.runner import Runner
lock = threading.Lock()
stopped = threading.Event()
class Service:
    def start(self): pass
    def request_stop(self):
        with lock:
            stopped.set()
    def stop(self): assert stopped.is_set()
def scan():
    with lock:
        os.kill(os.getpid(), signal.SIGTERM)
runner = Runner(scan_job=scan, services=[Service()], auxiliary_service_factory=lambda: [])
runner.run()
assert stopped.is_set()
assert not runner.services_started
assert not any(t.name == "coinoskobi-shutdown" for t in threading.enumerate())
print("clean shutdown")
'''], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "clean shutdown" in result.stdout


def test_run_exception_signals_workers_before_join(monkeypatch):
    entered, completed = threading.Event(), threading.Event()
    runner = Runner(auxiliary_service_factory=lambda: [])

    def paper():
        entered.set()
        assert runner._paper_runtime_stop.wait(2)
        completed.set()

    runner.scheduler.every(1, paper, "paper_manager")

    def fail():
        assert entered.wait(1)
        raise RuntimeError("loop failed")

    monkeypatch.setattr(runner.scheduler, "tick", fail)
    monkeypatch.setattr("app.core.runner.signal.signal", lambda *a: None)
    with pytest.raises(RuntimeError, match="loop failed"):
        runner.run()
    assert completed.is_set()
    assert runner.paper_runtime_status()["threads_alive"] == 0


def test_stop_is_idempotent_and_service_stop_survives_pipeline_error():
    calls = []
    runner = Runner(services=[SimpleNamespace(request_stop=lambda: calls.append("service"))],
                    auxiliary_service_factory=lambda: [])

    def failing_pipeline():
        calls.append("pipeline")
        raise RuntimeError("unavailable")

    runner.pipeline = SimpleNamespace(request_stop=failing_pipeline)
    runner.stop()
    runner.stop()
    assert calls == ["pipeline", "service"]
    assert runner._paper_runtime_stop.is_set()

def test_signal_handler_sets_stop_state_immediately():
    runner = Runner(auxiliary_service_factory=lambda: [])
    assert runner.running is True
    runner._handle_signal()
    assert runner.running is False


def test_pipeline_stop_propagates_before_unrelated_fast_watch_callback():
    pipeline_stopped = threading.Event()
    fast_watch_entered = threading.Event()
    release_fast_watch = threading.Event()

    class FastWatch:
        def request_stop(self):
            fast_watch_entered.set()
            assert release_fast_watch.wait(2)

    runner = Runner(auxiliary_service_factory=lambda: [])
    runner.pipeline = SimpleNamespace(request_stop=pipeline_stopped.set)
    runner.fast_watch_revisit = FastWatch()

    thread = threading.Thread(target=runner.stop)
    thread.start()
    assert pipeline_stopped.wait(0.5)
    assert fast_watch_entered.wait(0.5)
    release_fast_watch.set()
    thread.join(2)
    assert not thread.is_alive()


def test_pipeline_request_stop_reaches_scheduler_and_provider_first(monkeypatch):
    from app.pipeline.engine import PipelineEngine
    import app.chains.bsc as bsc

    calls = []

    class Stopper:
        def __init__(self, name):
            self.name = name

        def request_stop(self):
            calls.append(self.name)
            return True

    engine = PipelineEngine.__new__(PipelineEngine)
    engine.work_scheduler = Stopper("scheduler")
    engine.scanner = Stopper("scanner")
    engine.native_market_flow = Stopper("native")
    monkeypatch.setattr(
        bsc,
        "w3",
        SimpleNamespace(provider=Stopper("provider")),
    )

    assert engine.request_stop() is True
    assert calls == ["scheduler", "provider", "scanner", "native"]


def test_paper_batch_stops_between_positions_and_preserves_started_lifecycle():
    from app.paper.manager import PaperManager

    stopped = threading.Event()
    started = []
    committed = []

    manager = PaperManager.__new__(PaperManager)
    manager.replay_closed_outcomes = lambda: None
    manager.db = SimpleNamespace(
        open_positions=lambda: [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ]
    )
    manager.shutdown_requested = stopped.is_set

    def process_position(pos):
        started.append(pos["id"])
        committed.append(pos["id"])
        stopped.set()
        return {"position_id": pos["id"], "state": "COMMITTED"}

    manager._process_position = process_position

    result = manager.process()

    assert started == [1]
    assert committed == [1]
    assert result == [{"position_id": 1, "state": "COMMITTED"}]


def test_process_positions_does_not_start_manager_after_refresh_requests_stop():
    from app.pipeline.engine import PipelineEngine
    from app.pipeline.work_scheduler import WorkScheduler

    engine = PipelineEngine.__new__(PipelineEngine)
    engine.work_scheduler = WorkScheduler(max_workers=1)
    called = []
    engine.manager = SimpleNamespace(
        db=SimpleNamespace(open_positions=lambda: [{"id": 1}]),
        process=lambda: called.append("manager"),
        hybrid_exit_evidence=None,
    )
    engine._hybrid_exit_runtime_evidence = lambda *args, **kwargs: None

    def refresh():
        engine.work_scheduler.request_stop()
        return {"state": "REFRESHED"}

    engine.refresh_open_position_prices = refresh

    assert engine.process_positions() == []
    assert called == []
