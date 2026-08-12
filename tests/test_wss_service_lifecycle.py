import asyncio
import time

from app.core.runner import Runner
from app.dex.wss_service import (
    NativeWSSService,
)


class FakeRuntime:
    instances = []

    def __init__(
        self,
        url,
        pair,
        *,
        on_event=None,
        on_retraction=None,
        **kwargs,
    ):
        self.url = url
        self.pair = pair
        self.on_event = on_event
        self.on_retraction = (
            on_retraction
        )

        self.stop_requested = False
        self.started = False

        type(self).instances.append(
            self
        )

    async def run(self):
        self.started = True

        while not self.stop_requested:
            await asyncio.sleep(
                0.001
            )

        return self.status()

    def request_stop(self):
        self.stop_requested = True

    def status(self):
        return {
            "state": (
                "RUNNING"
                if self.started
                and not self.stop_requested
                else "STOPPING"
            ),
            "decision_authority": False,
            "execution_authority": False,
        }


def wait_for(
    predicate,
    timeout=2.0,
):
    deadline = (
        time.monotonic()
        + timeout
    )

    while (
        time.monotonic()
        < deadline
    ):
        if predicate():
            return True

        time.sleep(0.005)

    return False


def test_service_starts_runtime_in_owned_thread():
    FakeRuntime.instances.clear()

    service = NativeWSSService(
        "wss://example",
        "0xpair",
        runtime_factory=FakeRuntime,
    )

    assert service.start() is True

    assert wait_for(
        lambda: (
            bool(
                FakeRuntime.instances
            )
            and FakeRuntime.instances[
                0
            ].started
        )
    )

    status = service.status()

    assert status[
        "application_owned"
    ] is True

    assert status[
        "thread_alive"
    ] is True

    assert status[
        "runtime_present"
    ] is True

    assert service.stop() is True

    assert service.status()[
        "thread_alive"
    ] is False


def test_start_is_idempotent():
    FakeRuntime.instances.clear()

    service = NativeWSSService(
        "wss://example",
        "0xpair",
        runtime_factory=FakeRuntime,
    )

    assert service.start() is True

    assert wait_for(
        lambda: (
            len(
                FakeRuntime.instances
            )
            == 1
        )
    )

    assert service.start() is False

    assert len(
        FakeRuntime.instances
    ) == 1

    assert service.stop() is True


def test_stop_before_start_is_safe():
    service = NativeWSSService(
        "wss://example",
        "0xpair",
        runtime_factory=FakeRuntime,
    )

    assert service.stop() is False

    assert service.status()[
        "state"
    ] == "NOT_STARTED"


def test_service_authority_zero():
    service = NativeWSSService(
        "wss://example",
        "0xpair",
        runtime_factory=FakeRuntime,
    )

    status = service.status()

    assert status[
        "decision_authority"
    ] is False

    assert status[
        "paper_authority"
    ] is False

    assert status[
        "live_authority"
    ] is False

    assert status[
        "wallet_authority"
    ] is False

    assert status[
        "execution_authority"
    ] is False


class FakeService:
    def __init__(
        self,
        events,
    ):
        self.events = events
        self.name = "fake"

    def start(self):
        self.events.append(
            "start"
        )

    def stop(self):
        self.events.append(
            "stop"
        )

    def status(self):
        return {
            "name": self.name,
            "state": "OK",
        }


def test_runner_owns_service_start_and_stop():
    events = []

    service = FakeService(
        events
    )

    runner = Runner(
        services=[
            service
        ],
        sleep_func=lambda _: (
            runner.stop()
        ),
    )

    runner.run()

    assert events == [
        "start",
        "stop",
    ]

    assert (
        runner.services_started
        is False
    )


def test_runner_stops_services_on_scheduler_failure():
    events = []

    service = FakeService(
        events
    )

    runner = Runner(
        services=[
            service
        ],
        sleep_func=lambda _: None,
    )

    def explode():
        raise RuntimeError(
            "scheduler failure"
        )

    runner.scheduler.tick = (
        explode
    )

    try:
        runner.run()
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "expected scheduler failure"
        )

    assert events == [
        "start",
        "stop",
    ]
