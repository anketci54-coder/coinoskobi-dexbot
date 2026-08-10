from concurrent.futures import ThreadPoolExecutor, as_completed


class WorkScheduler:
    """
    Basit bounded worker scheduler.

    - token sayisina sabit batch kotasi uygulamaz
    - yalniz max_workers ile pahali concurrency'yi sinirlar
    - tek is hatasi digerlerini durdurmaz
    """

    def __init__(self, max_workers=8):
        self.max_workers = max_workers

    def process_queue(
        self,
        queue,
        worker,
    ):
        processed = 0
        failed = 0

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = {}

            while True:
                while len(futures) < self.max_workers:
                    row = queue.pop()

                    if row is None:
                        break

                    future = executor.submit(
                        worker,
                        row,
                    )

                    futures[future] = row

                if not futures:
                    break

                done = next(
                    as_completed(futures)
                )

                futures.pop(done)

                try:
                    done.result()
                    processed += 1
                except Exception:
                    failed += 1

        return {
            "processed": processed,
            "failed": failed,
            "pending": queue.pending_count,
        }
