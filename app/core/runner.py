import signal
import time

from app.core.logger import get_logger

log = get_logger()


class Runner:

    def __init__(
        self,
        scan_interval=300,
        position_interval=60,
    ):
        self.scan_interval = scan_interval
        self.position_interval = position_interval
        self.running = True

    def stop(self, *_):
        log.info("Shutdown requested...")
        self.running = False

    def run(self):

        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        log.info("Runner started.")

        last_scan = 0
        last_position = 0

        while self.running:

            now = time.time()

            if now - last_scan >= self.scan_interval:
                log.info("[SCAN] scheduled")
                last_scan = now

            if now - last_position >= self.position_interval:
                log.info("[POSITION] scheduled")
                last_position = now

            time.sleep(1)

        log.info("Runner stopped.")


if __name__ == "__main__":
    Runner(scan_interval=5, position_interval=2).run()
