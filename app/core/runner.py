import signal
import time

from app.core.logger import get_logger
from app.core.scheduler import Scheduler

log = get_logger()


class Runner:

    def __init__(self, scan_job=None, position_job=None):
        self.scheduler = Scheduler()

        if scan_job:
            self.scheduler.every(
                interval=300,
                func=scan_job,
                name="scanner",
            )

        if position_job:
            self.scheduler.every(
                interval=60,
                func=position_job,
                name="paper_manager",
            )

        self.running = True

    def stop(self, *_):
        log.info("Shutdown requested...")
        self.running = False

    def run(self):

        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        log.info("Runner started")

        while self.running:
            self.scheduler.tick()
            time.sleep(1)

        log.info("Runner stopped")
