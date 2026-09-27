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
