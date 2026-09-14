import signal
import threading
import time

from app.core.application_services import build_application_auxiliary_services
from app.core.logger import get_logger
from app.core.scheduler import Scheduler
from app.market_data.broker import MarketDataBroker
from app.pipeline.fast_watch_revisit import FastWatchRevisitJob
from app.pipeline.runtime_price_history import install_runtime_price_history_cache

log = get_logger()


PAPER_RUNTIME_JOB_NAMES = {
    "paper_manager",
    "paper_hot_manager",
}


def _application_pipeline(scan_job):
    """Resolve the PipelineEngine captured by build_application."""
    code = getattr(scan_job, "__code__", None)
    closure = getattr(scan_job, "__closure__", None)
    if code is None or not closure:
        return None

    try:
        captured = {
            name: cell.cell_contents
            for name, cell in zip(code.co_freevars, closure)
        }
    except (AttributeError, ValueError):
        return None

    return captured.get("pipeline")


def _application_intelligence(scan_job):
    """Resolve the intelligence owned by the captured PipelineEngine."""
    pipeline = _application_pipeline(scan_job)
    return getattr(pipeline, "intelligence", None)


class Runner:

    def __init__(
        self,
        scan_job=None,
        position_job=None,
        watch_probe_job=None,
        services=None,
        sleep_func=None,
        auxiliary_service_factory=None,
    ):
        self.scheduler = Scheduler()
        pipeline = (
            _application_pipeline(scan_job)
            if scan_job
            else None
        )

        if pipeline is not None:
            install_runtime_price_history_cache()

        self.pipeline = pipeline
        self._paper_lifecycle_lock = threading.RLock()
        self._paper_runtime_stop = threading.Event()
        self._paper_runtime_threads = []
        self._paper_runtime_jobs = []
        self._paper_runtime_started = False

        if scan_job:
            self.scheduler.every(
                interval=300,
                func=scan_job,
                name="scanner",
            )

        if pipeline is not None:
            # Keep all runtime market-data consumers behind the canonical
            # provider boundary. The broker adds no decision/execution
            # authority; provider cooldown/failover remains scanner-owned.
            scanner = getattr(pipeline, "scanner", None)
            if scanner is not None and not isinstance(scanner, MarketDataBroker):
                pipeline.scanner = MarketDataBroker(scanner)

            self.fast_watch_revisit = FastWatchRevisitJob(
                pipeline
            )
            self._bind_serialized_pipeline_positions()
        else:
            self.fast_watch_revisit = None

        if position_job:
            self.scheduler.every(
                interval=10,
                func=position_job,
                name="paper_manager",
            )

        if watch_probe_job:
            self.scheduler.every(
                interval=10,
                func=watch_probe_job,
                name="watch_probe_exit_sweeper",
            )

        self.services = list(
            services or []
        )

        if auxiliary_service_factory is None:
            auxiliary = build_application_auxiliary_services(
                intelligence=getattr(
                    pipeline,
                    "intelligence",
                    None,
                ),
            )
        else:
            auxiliary = (
                auxiliary_service_factory()
                if callable(auxiliary_service_factory)
                else []
            )
        self.services.extend(
            list(auxiliary or [])
        )

        self.sleep_func = (
            sleep_func
            or time.sleep
        )

        self.running = True
        self.services_started = False
        self.last_service_error = None

    def _bind_serialized_pipeline_positions(self):
        positions = getattr(
            self.pipeline,
            "process_positions",
            None,
        )

        if not callable(positions):
            return False

        if getattr(
            positions,
            "_coinoskobi_serialized_paper_lifecycle",
            False,
        ):
            return True

        lock = self._paper_lifecycle_lock
        original = positions

        def serialized_positions(*args, **kwargs):
            with lock:
                return original(*args, **kwargs)

        serialized_positions.__name__ = getattr(
            original,
            "__name__",
            "process_positions",
        )
        serialized_positions._coinoskobi_serialized_paper_lifecycle = True

        self.pipeline.process_positions = serialized_positions
        return True

    def _detach_paper_runtime_jobs(self):
        if self._paper_runtime_jobs:
            return list(self._paper_runtime_jobs)

        detached = []
        remaining = []

        for job in self.scheduler.jobs:
            if job.get("name") in PAPER_RUNTIME_JOB_NAMES:
                detached.append(job)
            else:
                remaining.append(job)

        if detached:
            self.scheduler.jobs = remaining
            self._paper_runtime_jobs = detached

        return list(detached)

    def _paper_runtime_loop(self, job):
        name = str(
            job.get("name")
            or "paper_runtime"
        )
        func = job.get("func")

        try:
            interval = max(
                0.1,
                float(job.get("interval") or 1.0),
            )
        except (TypeError, ValueError):
            interval = 1.0

        if not callable(func):
            return

        while (
            self.running
            and not self._paper_runtime_stop.is_set()
        ):
            started = time.monotonic()

            try:
                # The lock covers the caller's complete lifecycle region,
                # including temporary manager.price / hybrid_exit_evidence
                # setup, manager processing and teardown. Recheck shutdown
                # after acquiring it so a queued paper job cannot begin a new
                # lifecycle after stop() has already been requested.
                with self._paper_lifecycle_lock:
                    if (
                        not self.running
                        or self._paper_runtime_stop.is_set()
                    ):
                        break

                    func()
            except Exception:
                log.exception(
                    "Independent paper runtime failed: {}",
                    name,
                )

            elapsed = (
                time.monotonic()
                - started
            )
            delay = max(
                0.01,
                interval - elapsed,
            )

            if self._paper_runtime_stop.wait(delay):
                break

    def _start_paper_runtime(self):
        if self._paper_runtime_started:
            return False

        jobs = self._detach_paper_runtime_jobs()

        if not jobs:
            return False

        self._paper_runtime_stop.clear()
        self._paper_runtime_threads = []

        for job in jobs:
            name = str(
                job.get("name")
                or "paper_runtime"
            )
            thread = threading.Thread(
                target=self._paper_runtime_loop,
                args=(job,),
                name=f"coinoskobi-{name}",
                daemon=True,
            )
            self._paper_runtime_threads.append(
                thread
            )
            thread.start()

        self._paper_runtime_started = True

        log.info(
            "Independent paper runtime started jobs={}",
            [
                job.get("name")
                for job in jobs
            ],
        )

        return True

    def _stop_paper_runtime(self):
        if not self._paper_runtime_started:
            return

        self._paper_runtime_stop.set()

        for thread in self._paper_runtime_threads:
            if thread is threading.current_thread():
                continue

            # Provider calls used by open-position refreshes are bounded, so
            # shutdown must wait for the in-flight lifecycle region to exit
            # instead of declaring the runtime stopped while it can still
            # mutate paper state or use services that are about to stop.
            thread.join()

        self._paper_runtime_started = False

    def paper_runtime_status(self):
        return {
            "state": (
                "RUNNING"
                if self._paper_runtime_started
                else "STOPPED"
            ),
            "jobs": [
                job.get("name")
                for job in self._paper_runtime_jobs
            ],
            "threads_alive": sum(
                1
                for thread in self._paper_runtime_threads
                if thread.is_alive()
            ),
            "scanner_independent": True,
            "serialized_lifecycle_context": True,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def stop(self, *_):
        log.info(
            "Shutdown requested..."
        )

        self.running = False
        self.scheduler.request_stop()
        self._paper_runtime_stop.set()

        if self.fast_watch_revisit is not None:
            self.fast_watch_revisit.request_stop()

        pipeline_stop = getattr(
            self.pipeline,
            "request_stop",
            None,
        )

        if callable(pipeline_stop):
            pipeline_stop()
        else:
            work_scheduler = getattr(
                self.pipeline,
                "work_scheduler",
                None,
            )
            request_stop = getattr(
                work_scheduler,
                "request_stop",
                None,
            )

            if callable(request_stop):
                request_stop()

        for service in self.services:
            service_request_stop = getattr(
                service,
                "request_stop",
                None,
            )

            if callable(service_request_stop):
                try:
                    service_request_stop()
                except Exception:
                    log.exception(
                        "Service stop request failed: {}",
                        getattr(
                            service,
                            "name",
                            type(service).__name__,
                        ),
                    )

    def _start_services(self):
        if self.services_started:
            return

        started = []

        try:
            for service in self.services:
                service.start()
                started.append(service)

            self.services_started = True

        except Exception as exc:
            self.last_service_error = (
                f"{type(exc).__name__}: {exc}"
            )

            for service in reversed(
                started
            ):
                try:
                    service.stop()
                except Exception:
                    pass

            raise

    def _stop_services(self):
        errors = []

        for service in reversed(
            self.services
        ):
            try:
                service.stop()
            except Exception as exc:
                errors.append(
                    f"{type(exc).__name__}: {exc}"
                )

        self.services_started = False

        if errors:
            self.last_service_error = (
                "; ".join(errors)
            )

            log.error(
                "Service shutdown errors: {}",
                self.last_service_error,
            )

    def _start_fast_watch_revisit(self):
        if self.fast_watch_revisit is None:
            return False

        return self.fast_watch_revisit.start()

    def _stop_fast_watch_revisit(self):
        if self.fast_watch_revisit is None:
            return

        self.fast_watch_revisit.shutdown()

    def service_status(self):
        result = []

        for service in self.services:
            try:
                result.append(
                    service.status()
                )
            except Exception as exc:
                result.append({
                    "name": getattr(
                        service,
                        "name",
                        type(
                            service
                        ).__name__,
                    ),
                    "state": "STATUS_ERROR",
                    "last_error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                })

        return result

    def run(self):
        signal.signal(
            signal.SIGINT,
            self.stop,
        )

        signal.signal(
            signal.SIGTERM,
            self.stop,
        )

        log.info("Runner started")

        try:
            self._start_services()
            self._start_fast_watch_revisit()
            self._start_paper_runtime()

            while self.running:
                self.scheduler.tick()
                self.sleep_func(1)

        finally:
            # Finish any in-flight fast revisit before shutting down service
            # dependencies, so a committed paper decision cannot lose its
            # durable observer/promotion bookkeeping during SIGTERM.
            self._stop_fast_watch_revisit()
            self._stop_paper_runtime()
            self._stop_services()

            log.info(
                "Runner stopped"
            )
