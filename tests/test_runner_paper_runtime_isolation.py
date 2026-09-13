import threading
import time

from app.core.runner import Runner


def test_paper_manager_runs_while_scanner_tick_is_blocked():
    scan_started = threading.Event()
    scan_release = threading.Event()
    paper_seen = threading.Event()

    def scan_job():
        scan_started.set()
        scan_release.wait(1.0)
        return {"state": "RAN"}

    def position_job():
        paper_seen.set()
        return []

    runner = Runner(
        scan_job=scan_job,
        position_job=position_job,
        auxiliary_service_factory=lambda: [],
    )

    assert runner._start_paper_runtime() is True

    tick_thread = threading.Thread(
        target=runner.scheduler.tick,
        daemon=True,
    )
    tick_thread.start()

    assert scan_started.wait(0.5)
    assert paper_seen.wait(0.5)

    scan_release.set()
    tick_thread.join(timeout=1.0)
    runner._stop_paper_runtime()

    assert tick_thread.is_alive() is False


def test_hot_and_fallback_paper_jobs_leave_main_scheduler():
    fallback_seen = threading.Event()
    hot_seen = threading.Event()

    runner = Runner(
        position_job=lambda: fallback_seen.set(),
        auxiliary_service_factory=lambda: [],
    )

    runner.scheduler.every(
        interval=1,
        func=lambda: hot_seen.set(),
        name="paper_hot_manager",
    )

    before = {
        job["name"]
        for job in runner.scheduler.jobs
    }

    assert "paper_manager" in before
    assert "paper_hot_manager" in before

    assert runner._start_paper_runtime() is True

    after = {
        job["name"]
        for job in runner.scheduler.jobs
    }

    assert "paper_manager" not in after
    assert "paper_hot_manager" not in after
    assert fallback_seen.wait(0.5)
    assert hot_seen.wait(0.5)

    status = runner.paper_runtime_status()
    assert status["state"] == "RUNNING"
    assert status["threads_alive"] == 2
    assert status["scanner_independent"] is True
    assert status[
        "serialized_lifecycle_context"
    ] is True

    runner._stop_paper_runtime()


def test_full_lifecycle_context_is_serialized_across_paths():
    guard = threading.Lock()
    release = threading.Event()
    hot_entered = threading.Event()
    pipeline_entered = threading.Event()
    state = {
        "active": 0,
        "max_active": 0,
    }

    def critical(label):
        with guard:
            state["active"] += 1
            state["max_active"] = max(
                state["max_active"],
                state["active"],
            )

        if label == "hot":
            hot_entered.set()
            release.wait(0.5)
        else:
            pipeline_entered.set()

        time.sleep(0.02)

        with guard:
            state["active"] -= 1

    class Pipeline:
        scanner = None
        intelligence = None

        def process_positions(self):
            critical("pipeline")
            return []

        def run_cycle(self):
            return {"state": "RAN"}

    pipeline = Pipeline()

    def scan_job():
        return pipeline.run_cycle()

    runner = Runner(
        scan_job=scan_job,
        auxiliary_service_factory=lambda: [],
    )

    runner.scheduler.every(
        interval=1,
        func=lambda: critical("hot"),
        name="paper_hot_manager",
    )

    assert runner._start_paper_runtime() is True
    assert hot_entered.wait(0.5)

    scanner_lifecycle = threading.Thread(
        target=pipeline.process_positions,
        daemon=True,
    )
    scanner_lifecycle.start()

    time.sleep(0.05)

    # The hot path is still inside its full setup/process/teardown
    # critical region, so the scanner lifecycle must not enter yet.
    assert pipeline_entered.is_set() is False
    assert state["max_active"] == 1

    release.set()
    scanner_lifecycle.join(timeout=1.0)
    runner._stop_paper_runtime()

    assert scanner_lifecycle.is_alive() is False
    assert pipeline_entered.is_set() is True
    assert state["max_active"] == 1


def test_shutdown_waits_for_inflight_paper_lifecycle():
    entered = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def position_job():
        entered.set()
        release.wait(1.0)
        completed.set()
        return []

    runner = Runner(
        position_job=position_job,
        auxiliary_service_factory=lambda: [],
    )

    assert runner._start_paper_runtime() is True
    assert entered.wait(0.5)

    shutdown = threading.Thread(
        target=runner._stop_paper_runtime,
        daemon=True,
    )
    shutdown.start()

    time.sleep(0.05)

    assert shutdown.is_alive() is True
    assert runner._paper_runtime_started is True
    assert completed.is_set() is False

    release.set()
    shutdown.join(timeout=1.0)

    assert shutdown.is_alive() is False
    assert completed.is_set() is True
    assert runner._paper_runtime_started is False
    assert runner.paper_runtime_status()[
        "threads_alive"
    ] == 0


def test_shutdown_prevents_queued_paper_lifecycle_from_starting():
    active_entered = threading.Event()
    active_release = threading.Event()
    queued_called = threading.Event()

    runner = Runner(
        auxiliary_service_factory=lambda: [],
    )

    active_job = {
        "name": "paper_manager",
        "interval": 10,
        "func": lambda: (
            active_entered.set(),
            active_release.wait(1.0),
        ),
    }
    queued_job = {
        "name": "paper_hot_manager",
        "interval": 1,
        "func": lambda: queued_called.set(),
    }

    active_thread = threading.Thread(
        target=runner._paper_runtime_loop,
        args=(active_job,),
        daemon=True,
    )
    queued_thread = threading.Thread(
        target=runner._paper_runtime_loop,
        args=(queued_job,),
        daemon=True,
    )

    active_thread.start()
    assert active_entered.wait(0.5)

    queued_thread.start()
    time.sleep(0.05)

    runner.running = False
    runner._paper_runtime_stop.set()

    active_release.set()
    active_thread.join(timeout=1.0)
    queued_thread.join(timeout=1.0)

    assert active_thread.is_alive() is False
    assert queued_thread.is_alive() is False
    assert queued_called.is_set() is False
