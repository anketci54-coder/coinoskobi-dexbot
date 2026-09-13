import time
from typing import Callable

from app.core.logger import get_logger

log = get_logger()


class Scheduler:

    def __init__(self):
        self.jobs = []
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True
        return True

    def every(self, interval: int, func: Callable, name: str = ""):
        self.jobs.append({
            "interval": interval,
            "next": time.time(),
            "func": func,
            "name": name or func.__name__,
        })

    def tick(self):

        if self._stop_requested:
            return

        now = time.time()

        for job in self.jobs:

            if self._stop_requested:
                break

            if now < job["next"]:
                continue

            log.info("[JOB] {}", job["name"])

            try:
                job["func"]()
            except Exception:
                log.exception(job["name"])

            job["next"] = now + job["interval"]

            if self._stop_requested:
                break
