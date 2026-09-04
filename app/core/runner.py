import signal
import time

from app.core.application_services import build_application_auxiliary_services
from app.core.logger import get_logger
from app.core.scheduler import Scheduler

log = get_logger()


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

        if scan_job:
            self.scheduler.every(
                interval=300,
                func=scan_job,
                name="scanner",
            )

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

        factory = (
            auxiliary_service_factory
            if auxiliary_service_factory is not None
            else build_application_auxiliary_services
        )
        auxiliary = factory() if callable(factory) else []
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
            self._stop_services()

            log.info(
                "Runner stopped"
            )
