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

    runner._stop_paper_runtime()


def test_manager_process_is_serialized_across_runtime_paths():
    class Manager:
        def __init__(self):
            self.guard = threading.Lock()
            self.active = 0
            self.max_active = 0

        def process(self):
            with self.guard:
                self.active += 1
                self.max_active = max(
                    self.max_active,
                    self.active,
                )

            time.sleep(0.05)

            with self.guard:
                self.active -= 1

            return []

    class Pipeline:
        scanner = None

        def __init__(self):
            self.manager = Manager()
            self.intelligence = None

        def run_cycle(self):
            return {"state": "RAN"}

    pipeline = Pipeline()

    def scan_job():
        return pipeline.run_cycle()

    Runner(
        scan_job=scan_job,
        auxiliary_service_factory=lambda: [],
    )

    first = threading.Thread(
        target=pipeline.manager.process
    )
    second = threading.Thread(
        target=pipeline.manager.process
    )

    first.start()
    second.start()
    first.join(timeout=1.0)
    second.join(timeout=1.0)

    assert first.is_alive() is False
    assert second.is_alive() is False
    assert pipeline.manager.max_active == 1
