import time
from typing import Callable

from app.core.logger import get_logger

log = get_logger()


class Scheduler:

    def __init__(self):
        self.jobs = []

    def every(self, interval: int, func: Callable, name: str = ""):
        self.jobs.append({
            "interval": interval,
            "next": time.time(),
            "func": func,
            "name": name or func.__name__,
        })

    def tick(self):

        now = time.time()

        for job in self.jobs:

            if now < job["next"]:
                continue

            log.info("[JOB] {}", job["name"])

            try:
                job["func"]()
            except Exception:
                log.exception(job["name"])

            job["next"] = now + job["interval"]
