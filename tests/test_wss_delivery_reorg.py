import asyncio
import json
from collections import deque

from app.dex.native_ingestion import (
    SWAP_TOPIC,
)
from app.dex.wss_runtime import (
    NativeWSSRuntime,
)


def ack(subscription="sub-1"):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": subscription,
    }


def event(
    tx,
    idx,
    block,
    *,
    subscription="sub-1",
    removed=False,
):
    return {
        "jsonrpc": "2.0",
        "method": "eth_subscription",
        "params": {
            "subscription": subscription,
            "result": {
                "transactionHash": tx,
                "logIndex": idx,
                "blockNumber": block,
                "removed": removed,
                "topics": [
                    SWAP_TOPIC
                ],
            },
        },
    }


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = deque(
            messages
        )
        self.sent = []

    async def send(self, payload):
        self.sent.append(
            json.loads(payload)
        )

    async def recv(self):
        if not self.messages:
            raise ConnectionError(
                "fake exhausted"
            )

        value = self.messages.popleft()

        if isinstance(
            value,
            BaseException,
        ):
            raise value

        return json.dumps(value)


class FakeConnection:
    def __init__(self, ws):
        self.ws = ws

    async def __aenter__(self):
        return self.ws

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False


class FakeFactory:
    def __init__(self, sockets):
        self.sockets = deque(
            sockets
        )

    def __call__(
        self,
        url,
        **kwargs,
    ):
        return FakeConnection(
            self.sockets.popleft()
        )


def run(value):
    return asyncio.run(value)


def test_wrong_subscription_is_rejected():
    ws = FakeWebSocket([
        ack("sub-1"),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            subscription="stale-sub",
        ),
        event(
            "0xbbb",
            "0x2",
            "0x10",
            subscription="sub-1",
        ),
    ])

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([
            ws
        ]),
    )

    result = run(
        runtime.run(
            max_events=1
        )
    )

    assert (
        result[
            "subscription_mismatch_count"
        ]
        == 1
    )

    assert result[
        "rejected_count"
    ] == 1

    assert result[
        "accepted_count"
    ] == 1


def test_callback_failure_does_not_ack_event():
    attempts = []

    async def callback(row):
        attempts.append(
            row["event_identity"]
        )

        if len(attempts) == 1:
            raise RuntimeError(
                "downstream failed"
            )

    first = FakeWebSocket([
        ack("sub-1"),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            subscription="sub-1",
        ),
    ])

    second = FakeWebSocket([
        ack("sub-2"),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            subscription="sub-2",
        ),
    ])

    async def no_sleep(_):
        pass

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([
            first,
            second,
        ]),
        sleep_func=no_sleep,
        max_reconnects=1,
        on_event=callback,
    )

    result = run(
        runtime.run(
            max_events=1
        )
    )

    assert attempts == [
        "0xaaa:0x1",
        "0xaaa:0x1",
    ]

    assert result[
        "delivery_failure_count"
    ] == 1

    assert result[
        "reconnect_count"
    ] == 1

    assert result[
        "duplicate_count"
    ] == 0

    assert result[
        "accepted_count"
    ] == 1

    assert result[
        "seen_size"
    ] == 1


def test_explicit_false_is_negative_ack():
    attempts = 0

    async def callback(row):
        nonlocal attempts
        attempts += 1

        return attempts > 1

    first = FakeWebSocket([
        ack("sub-1"),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            subscription="sub-1",
        ),
    ])

    second = FakeWebSocket([
        ack("sub-2"),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            subscription="sub-2",
        ),
    ])

    async def no_sleep(_):
        pass

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([
            first,
            second,
        ]),
        sleep_func=no_sleep,
        max_reconnects=1,
        on_event=callback,
    )

    result = run(
        runtime.run(
            max_events=1
        )
    )

    assert attempts == 2
    assert result[
        "delivery_failure_count"
    ] == 1

    assert result[
        "accepted_count"
    ] == 1


def test_seen_event_can_be_retracted_and_replayed():
    delivered = []

    async def callback(row):
        delivered.append(
            (
                row["delivery_kind"],
                row["event_identity"],
            )
        )

    async def retraction_callback(row):
        delivered.append(
            (
                row["delivery_kind"],
                row["event_identity"],
            )
        )

    original = event(
        "0xaaa",
        "0x1",
        "0x10",
    )

    removed = event(
        "0xaaa",
        "0x1",
        "0x10",
        removed=True,
    )

    replay = event(
        "0xaaa",
        "0x1",
        "0x10",
    )

    ws = FakeWebSocket([
        ack(),
        original,
        removed,
        replay,
    ])

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([
            ws
        ]),
        on_event=callback,
        on_retraction=retraction_callback,
    )

    result = run(
        runtime.run(
            max_events=2
        )
    )

    assert delivered == [
        (
            "EVENT",
            "0xaaa:0x1",
        ),
        (
            "RETRACTION",
            "0xaaa:0x1",
        ),
        (
            "EVENT",
            "0xaaa:0x1",
        ),
    ]

    assert result[
        "accepted_count"
    ] == 2

    assert result[
        "removed_count"
    ] == 1

    assert result[
        "retraction_count"
    ] == 1

    assert result[
        "duplicate_count"
    ] == 0


def test_removed_event_is_not_hidden_by_seen_set():
    delivered = []
    retractions = []

    async def callback(row):
        delivered.append(
            row["delivery_kind"]
        )

    async def retraction_callback(row):
        retractions.append(
            row["delivery_kind"]
        )

    ws = FakeWebSocket([
        ack(),
        event(
            "0xaaa",
            "0x1",
            "0x10",
        ),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            removed=True,
        ),
        event(
            "0xbbb",
            "0x2",
            "0x11",
        ),
    ])

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([
            ws
        ]),
        on_event=callback,
        on_retraction=retraction_callback,
    )

    result = run(
        runtime.run(
            max_events=2
        )
    )

    assert delivered == [
        "EVENT",
        "EVENT",
    ]

    assert retractions == [
        "RETRACTION",
    ]

    assert result[
        "removed_count"
    ] == 1


def test_failed_retraction_does_not_forget_seen():
    calls = []
    retractions = []

    async def callback(row):
        calls.append(
            row["delivery_kind"]
        )

    async def retraction_callback(row):
        retractions.append(
            row["delivery_kind"]
        )

        raise RuntimeError(
            "retraction downstream failed"
        )

    ws = FakeWebSocket([
        ack(),
        event(
            "0xaaa",
            "0x1",
            "0x10",
        ),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            removed=True,
        ),
    ])

    async def no_sleep(_):
        pass

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([
            ws
        ]),
        sleep_func=no_sleep,
        max_reconnects=0,
        on_event=callback,
        on_retraction=retraction_callback,
    )

    result = run(
        runtime.run()
    )

    assert calls == [
        "EVENT",
    ]

    assert retractions == [
        "RETRACTION",
    ]

    assert result[
        "delivery_failure_count"
    ] == 1

    assert result[
        "seen_size"
    ] == 1

    assert result[
        "removed_count"
    ] == 0


def test_status_exposes_delivery_contract():
    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([]),
    )

    r = runtime.status()

    assert (
        r["delivery_semantics"]
        == "CALLBACK_BEFORE_ACK_AT_LEAST_ONCE"
    )

    assert (
        r["retraction_supported"]
        is True
    )

    assert (
        r["separate_retraction_callback"]
        is True
    )

    assert (
        r["subscription_validation"]
        is True
    )

    assert r[
        "decision_authority"
    ] is False

    assert r[
        "execution_authority"
    ] is False
