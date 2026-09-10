import signal
import time

from app.config.scanner import (
    FAST_WATCH_REVISIT_SECONDS,
)
from app.core.application_services import build_application_auxiliary_services
from app.core.logger import get_logger
from app.core.scheduler import Scheduler
from app.pipeline.fast_watch_revisit import FastWatchRevisitJob

log = get_logger()


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

        if scan_job:
            self.scheduler.every(
                interval=300,
                func=scan_job,
                name="scanner",
            )

        if pipeline is not None:
            self.fast_watch_revisit = FastWatchRevisitJob(
                pipeline
            )
            self.scheduler.every(
                interval=FAST_WATCH_REVISIT_SECONDS,
                func=self.fast_watch_revisit.run_cycle,
                name="fast_watch_revisit",
            )
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

    def stop(self, *_):
        log.info(
            "Shutdown requested..."
        )

        self.running = False

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

            while self.running:
                self.scheduler.tick()
                self.sleep_func(1)

        finally:
            # Finish any in-flight fast revisit before shutting down service
            # dependencies, so a committed paper decision cannot lose its
            # durable observer/promotion bookkeeping during SIGTERM.
            self._stop_fast_watch_revisit()
            self._stop_services()

            log.info(
                "Runner stopped"
            )
