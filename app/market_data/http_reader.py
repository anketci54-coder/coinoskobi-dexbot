"""Cancellable waits for read-only, fully buffered HTTP GETs.

Requests' socket timeouts do not bound DNS or a trickling response. Keep only
the transport in daemon threads: no parsing, cache writes, or PAPER lifecycle
work may run there. Cancellation discards the response and never joins the
transport. A fixed slot limit also bounds stranded transports.
"""

import threading


class HTTPReadCancelled(RuntimeError):
    pass


class CancellableHTTPReader:
    POLL_SECONDS = 0.05

    def __init__(self, stop_event=None, *, max_inflight=4):
        self.stop_event = stop_event or threading.Event()
        self._slots = threading.BoundedSemaphore(max_inflight)

    def request_stop(self):
        self.stop_event.set()
        return True

    def raise_if_stopping(self):
        if self.stop_event.is_set():
            raise HTTPReadCancelled("market HTTP shutdown requested")

    def get(self, get, url, **kwargs):
        # stream=True would move blocking body reads back onto the caller.
        if kwargs.get("stream"):
            raise ValueError("buffered GET required")
        while True:
            self.raise_if_stopping()
            if self._slots.acquire(timeout=self.POLL_SECONDS):
                break

        done = threading.Event()
        result = []
        errors = []

        def read():
            try:
                self.raise_if_stopping()
                response = get(url, **kwargs)
                # Requests has buffered the body; close sockets even when the
                # caller has already cancelled. Response.json() stays usable.
                close = getattr(response, "close", None)
                if callable(close):
                    close()
                result.append(response)
            except Exception as exc:
                errors.append(exc)
            finally:
                self._slots.release()
                done.set()

        thread = threading.Thread(target=read, name="market-http-read", daemon=True)
        try:
            self.raise_if_stopping()
            thread.start()
        except BaseException:
            self._slots.release()
            raise
        while not done.wait(self.POLL_SECONDS):
            self.raise_if_stopping()
        self.raise_if_stopping()
        if errors:
            raise errors[0]
        return result[0]
