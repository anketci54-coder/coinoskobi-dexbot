from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class WorkSchedulerCancelled(Exception):
    pass


LANE_WARM = "WARM"
LANE_PARTIAL = "PARTIAL"
LANE_COLD = "COLD"

LANE_ORDER = (
    LANE_WARM,
    LANE_PARTIAL,
    LANE_COLD,
)


class WorkScheduler:
    """
    Basit bounded worker scheduler.

    Oncelik:
    WARM -> PARTIAL -> COLD

    Ayni lane icinde:
    chain round-robin uygulanir.

    Boylece:
    - tek chain tum kapasiteyi kullanabilir
    - ikinci chain varsa starvation yasamaz
    - token sayisina sabit batch kotasi uygulanmaz
    """

    def __init__(self, max_workers=8):
        self.max_workers = max_workers
        self._stop_event = threading.Event()

    def request_stop(self):
        self._stop_event.set()
        return True

    def is_stopping(self):
        return self._stop_event.is_set()

    @staticmethod
    def lane(row):
        conveyor = row.get("conveyor") or {}

        state = conveyor.get(
            "cache_state",
            LANE_COLD,
        )

        if state in LANE_ORDER:
            return state

        return LANE_COLD

    @staticmethod
    def chain(row):
        value = row.get("chain") or "bsc"

        return str(value).strip().lower()

    def _drain_by_lane_and_chain(
        self,
        queue,
    ):
        lanes = {
            LANE_WARM: {},
            LANE_PARTIAL: {},
            LANE_COLD: {},
        }

        counts = {
            LANE_WARM: 0,
            LANE_PARTIAL: 0,
            LANE_COLD: 0,
        }

        while True:
            row = queue.pop()

            if row is None:
                break

            lane = self.lane(row)
            chain = self.chain(row)

            chain_queue = lanes[lane].setdefault(
                chain,
                deque(),
            )

            chain_queue.append(row)
            counts[lane] += 1

        return lanes, counts

    @staticmethod
    def _round_robin_rows(
        chain_queues,
    ):
        if not chain_queues:
            return

        active = deque(
            chain_queues.keys()
        )

        while active:
            chain = active.popleft()

            items = chain_queues[chain]

            if not items:
                continue

            yield items.popleft()

            if items:
                active.append(chain)

    def _ordered_rows(
        self,
        lanes,
    ):
        for lane in LANE_ORDER:
            for row in self._round_robin_rows(
                lanes[lane]
            ):
                yield (
                    lane,
                    self.chain(row),
                    row,
                )

    def process_queue(
        self,
        queue,
        worker,
    ):
        lanes, lane_counts = (
            self._drain_by_lane_and_chain(
                queue
            )
        )

        processed = 0
        failed = 0

        lane_processed = {
            LANE_WARM: 0,
            LANE_PARTIAL: 0,
            LANE_COLD: 0,
        }

        lane_failed = {
            LANE_WARM: 0,
            LANE_PARTIAL: 0,
            LANE_COLD: 0,
        }

        chain_processed = {}
        chain_failed = {}

        ordered_rows = iter(
            self._ordered_rows(
                lanes
            )
        )

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = {}
            exhausted = False

            while (
                not exhausted
                or futures
            ):

                if self._stop_event.is_set():
                    exhausted = True

                    for future in list(futures):
                        if future.cancel():
                            futures.pop(future, None)

                    if not futures:
                        break

                while (
                    not exhausted
                    and not self._stop_event.is_set()
                    and len(futures)
                    < self.max_workers
                ):
                    try:
                        lane, chain, row = next(
                            ordered_rows
                        )
                    except StopIteration:
                        exhausted = True
                        break

                    future = executor.submit(
                        worker,
                        row,
                    )

                    futures[future] = (
                        lane,
                        chain,
                    )

                if not futures:
                    continue

                done = next(
                    as_completed(futures)
                )

                lane, chain = futures.pop(
                    done
                )

                try:
                    done.result()

                    processed += 1

                    lane_processed[
                        lane
                    ] += 1

                    chain_processed[
                        chain
                    ] = (
                        chain_processed.get(
                            chain,
                            0,
                        )
                        + 1
                    )

                except WorkSchedulerCancelled:
                    pass

                except Exception:
                    failed += 1

                    lane_failed[
                        lane
                    ] += 1

                    chain_failed[
                        chain
                    ] = (
                        chain_failed.get(
                            chain,
                            0,
                        )
                        + 1
                    )

        total_input = sum(
            lane_counts.values()
        )

        skipped = max(
            0,
            total_input - processed - failed,
        )

        return {
            "processed": processed,
            "failed": failed,
            "pending": queue.pending_count,
            "stopped": self._stop_event.is_set(),
            "skipped": skipped,
            "warm": {
                "input": lane_counts[
                    LANE_WARM
                ],
                "processed": lane_processed[
                    LANE_WARM
                ],
                "failed": lane_failed[
                    LANE_WARM
                ],
            },
            "partial": {
                "input": lane_counts[
                    LANE_PARTIAL
                ],
                "processed": lane_processed[
                    LANE_PARTIAL
                ],
                "failed": lane_failed[
                    LANE_PARTIAL
                ],
            },
            "cold": {
                "input": lane_counts[
                    LANE_COLD
                ],
                "processed": lane_processed[
                    LANE_COLD
                ],
                "failed": lane_failed[
                    LANE_COLD
                ],
            },
            "chains": {
                "processed": chain_processed,
                "failed": chain_failed,
            },
        }
