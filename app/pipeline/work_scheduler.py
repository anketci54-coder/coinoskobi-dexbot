from concurrent.futures import ThreadPoolExecutor, as_completed


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

    Conveyor cache state yalniz scheduling maliyet sinifidir.

    WARM:
    - analyzer cache hit
    - RPC beklenmez

    PARTIAL:
    - mevcut analyzer cache hitleri tekrar RPC yapmaz
    - yalniz eksik analyzer pahali olabilir

    COLD:
    - tam analyzer yolu pahali olabilir

    Token sayisina sabit batch kotasi uygulanmaz.
    """

    def __init__(self, max_workers=8):
        self.max_workers = max_workers

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

    def _drain_by_lane(self, queue):
        lanes = {
            LANE_WARM: [],
            LANE_PARTIAL: [],
            LANE_COLD: [],
        }

        while True:
            row = queue.pop()

            if row is None:
                break

            lanes[
                self.lane(row)
            ].append(row)

        return lanes

    def process_queue(
        self,
        queue,
        worker,
    ):
        lanes = self._drain_by_lane(
            queue
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

        ordered_rows = []

        for lane in LANE_ORDER:
            for row in lanes[lane]:
                ordered_rows.append(
                    (
                        lane,
                        row,
                    )
                )

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = {}
            next_index = 0

            while (
                next_index < len(ordered_rows)
                or futures
            ):

                while (
                    next_index < len(ordered_rows)
                    and len(futures) < self.max_workers
                ):
                    lane, row = ordered_rows[
                        next_index
                    ]

                    next_index += 1

                    future = executor.submit(
                        worker,
                        row,
                    )

                    futures[future] = lane

                if not futures:
                    continue

                done = next(
                    as_completed(futures)
                )

                lane = futures.pop(done)

                try:
                    done.result()

                    processed += 1
                    lane_processed[lane] += 1

                except Exception:
                    failed += 1
                    lane_failed[lane] += 1

        return {
            "processed": processed,
            "failed": failed,
            "pending": queue.pending_count,
            "warm": {
                "input": len(
                    lanes[LANE_WARM]
                ),
                "processed": lane_processed[
                    LANE_WARM
                ],
                "failed": lane_failed[
                    LANE_WARM
                ],
            },
            "partial": {
                "input": len(
                    lanes[LANE_PARTIAL]
                ),
                "processed": lane_processed[
                    LANE_PARTIAL
                ],
                "failed": lane_failed[
                    LANE_PARTIAL
                ],
            },
            "cold": {
                "input": len(
                    lanes[LANE_COLD]
                ),
                "processed": lane_processed[
                    LANE_COLD
                ],
                "failed": lane_failed[
                    LANE_COLD
                ],
            },
        }
