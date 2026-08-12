import asyncio
import threading

from app.dex.wss_runtime import NativeWSSRuntime


class NativeWSSService:
    """
    Application-owned lifecycle wrapper for NativeWSSRuntime.

    The service:
    - owns one background thread
    - owns one asyncio event loop
    - starts/stops idempotently
    - exposes bounded health/status
    - never grants decision/trade/execution authority

    Event consumers are injected explicitly.
    """

    def __init__(
        self,
        url,
        pair,
        *,
        runtime_factory=None,
        on_event=None,
        on_retraction=None,
        join_timeout=10.0,
        runtime_kwargs=None,
    ):
        if not url:
            raise ValueError("url required")

        if not pair:
            raise ValueError("pair required")

        self.url = url
        self.pair = pair

        self.runtime_factory = (
            runtime_factory
            or NativeWSSRuntime
        )

        self.on_event = on_event
        self.on_retraction = (
            on_retraction
        )

        self.join_timeout = max(
            0.1,
            float(join_timeout),
        )

        self.runtime_kwargs = dict(
            runtime_kwargs or {}
        )

        self._lock = threading.RLock()
        self._thread = None
        self._loop = None
        self._runtime = None

        self._started = False
        self._stopping = False

        self.start_count = 0
        self.stop_count = 0
        self.failure_count = 0

        self.last_error = None

    def bind_callbacks(
        self,
        *,
        on_event=None,
        on_retraction=None,
    ):
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                raise RuntimeError(
                    "cannot rebind callbacks while running"
                )

            self.on_event = on_event
            self.on_retraction = (
                on_retraction
            )

        return {
            "state": "BOUND",
            "event_callback": (
                on_event is not None
            ),
            "retraction_callback": (
                on_retraction is not None
            ),
            "decision_authority": False,
            "execution_authority": False,
        }

    @property
    def name(self):
        return "native_wss"

    def start(self):
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return False

            self._started = True
            self._stopping = False
            self.last_error = None

            thread = threading.Thread(
                target=self._thread_main,
                name="coinoskobi-native-wss",
                daemon=True,
            )

            self._thread = thread
            self.start_count += 1

            thread.start()

            return True

    def stop(self):
        with self._lock:
            thread = self._thread
            loop = self._loop
            runtime = self._runtime

            if thread is None:
                return False

            self._stopping = True

            if runtime is not None:
                runtime.request_stop()

            if (
                loop is not None
                and loop.is_running()
            ):
                loop.call_soon_threadsafe(
                    lambda: None
                )

        if (
            thread is not None
            and thread.is_alive()
            and thread
            is not threading.current_thread()
        ):
            thread.join(
                timeout=self.join_timeout
            )

        with self._lock:
            self.stop_count += 1

            alive = bool(
                self._thread
                and self._thread.is_alive()
            )

            if not alive:
                self._thread = None

            self._stopping = False

            return not alive

    def _build_runtime(self):
        return self.runtime_factory(
            self.url,
            self.pair,
            on_event=self.on_event,
            on_retraction=(
                self.on_retraction
            ),
            **self.runtime_kwargs,
        )

    def _thread_main(self):
        loop = asyncio.new_event_loop()

        with self._lock:
            self._loop = loop

        try:
            asyncio.set_event_loop(loop)

            runtime = self._build_runtime()

            with self._lock:
                self._runtime = runtime

            loop.run_until_complete(
                runtime.run()
            )

        except Exception as exc:
            with self._lock:
                self.failure_count += 1
                self.last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

        finally:
            try:
                pending = asyncio.all_tasks(
                    loop
                )

                for task in pending:
                    task.cancel()

                if pending:
                    loop.run_until_complete(
                        asyncio.gather(
                            *pending,
                            return_exceptions=True,
                        )
                    )
            finally:
                loop.close()

                with self._lock:
                    self._loop = None
                    self._runtime = None

    def status(self):
        with self._lock:
            thread_alive = bool(
                self._thread
                and self._thread.is_alive()
            )

            runtime = self._runtime

            runtime_status = (
                runtime.status()
                if runtime is not None
                else None
            )

            if self.last_error:
                state = "FAILED"
            elif thread_alive:
                state = "RUNNING"
            elif self._started:
                state = "STOPPED"
            else:
                state = "NOT_STARTED"

            return {
                "name": self.name,
                "state": state,
                "thread_alive": (
                    thread_alive
                ),
                "runtime_present": (
                    runtime is not None
                ),
                "runtime_status": (
                    runtime_status
                ),
                "start_count": (
                    self.start_count
                ),
                "stop_count": (
                    self.stop_count
                ),
                "failure_count": (
                    self.failure_count
                ),
                "last_error": (
                    self.last_error
                ),
                "application_owned": True,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            }
