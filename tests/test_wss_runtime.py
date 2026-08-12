import asyncio
import json
from collections import deque

from app.dex.native_ingestion import (
    SWAP_TOPIC,
    SYNC_TOPIC,
)
from app.dex.wss_runtime import (
    NativeWSSRuntime,
)


def event(
    tx,
    idx,
    block,
    *,
    topic=SWAP_TOPIC,
    removed=False,
    subscription="sub-1",
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
                "topics": [topic],
            },
        },
    }


class FakeWebSocket:
    def __init__(
        self,
        messages,
    ):
        self.messages = deque(
            messages
        )
        self.sent = []
        self.closed = False

    async def send(self, payload):
        self.sent.append(
            json.loads(payload)
        )

    async def recv(self):
        if not self.messages:
            raise ConnectionError(
                "fake exhausted"
            )

        item = self.messages.popleft()

        if isinstance(
            item,
            BaseException,
        ):
            raise item

        return json.dumps(
            item
        )

    async def close(self):
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        websocket,
    ):
        self.websocket = websocket

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        await self.websocket.close()


class FakeFactory:
    def __init__(
        self,
        connections,
    ):
        self.connections = deque(
            connections
        )
        self.calls = 0
        self.kwargs = []

    def __call__(
        self,
        url,
        **kwargs,
    ):
        self.calls += 1
        self.kwargs.append(
            kwargs
        )

        if not self.connections:
            raise ConnectionError(
                "no fake connection"
            )

        return FakeConnection(
            self.connections.popleft()
        )


def ack(subscription="sub-1"):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": subscription,
    }


def run(coro):
    return asyncio.run(coro)


def test_connect_subscribe_receive_unsubscribe():
    ws = FakeWebSocket([
        ack(),
        event(
            "0xaaa",
            "0x1",
            "0x10",
        ),
        event(
            "0xbbb",
            "0x2",
            "0x10",
            topic=SYNC_TOPIC,
        ),
    ])

    factory = FakeFactory([
        ws
    ])

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=factory,
    )

    result = run(
        runtime.run(
            max_events=2
        )
    )

    assert result[
        "accepted_count"
    ] == 2

    assert result[
        "reconnect_count"
    ] == 0

    assert ws.sent[0][
        "method"
    ] == "eth_subscribe"

    assert ws.sent[-1][
        "method"
    ] == "eth_unsubscribe"


def test_duplicate_is_suppressed():
    duplicate = event(
        "0xaaa",
        "0x1",
        "0x10",
    )

    ws = FakeWebSocket([
        ack(),
        duplicate,
        duplicate,
        event(
            "0xbbb",
            "0x2",
            "0x10",
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
            max_events=2
        )
    )

    assert result[
        "accepted_count"
    ] == 2

    assert result[
        "duplicate_count"
    ] == 1


def test_removed_log_not_accepted():
    ws = FakeWebSocket([
        ack(),
        event(
            "0xaaa",
            "0x1",
            "0x10",
            removed=True,
        ),
        event(
            "0xbbb",
            "0x2",
            "0x10",
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

    assert result[
        "removed_count"
    ] == 1

    assert result[
        "accepted_count"
    ] == 1


def test_out_of_order_not_accepted():
    ws = FakeWebSocket([
        ack(),
        event(
            "0xaaa",
            "0x2",
            "0x20",
        ),
        event(
            "0xbbb",
            "0x1",
            "0x10",
        ),
        event(
            "0xccc",
            "0x3",
            "0x20",
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
            max_events=2
        )
    )

    assert result[
        "out_of_order_count"
    ] == 1

    assert result[
        "accepted_count"
    ] == 2


def test_reconnect_after_disconnect():
    first = FakeWebSocket([
        ack(),
        ConnectionError(
            "disconnect"
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

    factory = FakeFactory([
        first,
        second,
    ])

    sleeps = []

    async def fake_sleep(
        seconds,
    ):
        sleeps.append(
            seconds
        )

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=factory,
        sleep_func=fake_sleep,
        max_reconnects=2,
    )

    result = run(
        runtime.run(
            max_events=1
        )
    )

    assert factory.calls == 2

    assert result[
        "reconnect_count"
    ] == 1

    assert result[
        "accepted_count"
    ] == 1

    assert sleeps == [1.0]


def test_reconnect_is_bounded():
    factory = FakeFactory([
        FakeWebSocket([
            ack(),
            ConnectionError("one"),
        ]),
        FakeWebSocket([
            ack(),
            ConnectionError("two"),
        ]),
        FakeWebSocket([
            ack(),
            ConnectionError("three"),
        ]),
    ])

    async def no_sleep(_):
        pass

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=factory,
        sleep_func=no_sleep,
        max_reconnects=2,
    )

    result = run(
        runtime.run(
            max_events=1
        )
    )

    assert factory.calls == 3
    assert result[
        "reconnect_count"
    ] == 2

    assert result[
        "accepted_count"
    ] == 0

    assert result[
        "state"
    ] == "DISCONNECTED"


def test_buffer_is_bounded():
    messages = [
        ack()
    ]

    for i in range(100):
        messages.append(
            event(
                f"0x{i:064x}",
                hex(i),
                hex(100 + i),
            )
        )

    ws = FakeWebSocket(
        messages
    )

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        max_buffer=8,
        connect_factory=FakeFactory([
            ws
        ]),
    )

    result = run(
        runtime.run(
            max_events=100
        )
    )

    assert result[
        "accepted_count"
    ] == 100

    assert result[
        "buffer_size"
    ] == 8

    assert result[
        "buffer_dropped"
    ] == 92


def test_seen_memory_is_bounded():
    messages = [
        ack()
    ]

    for i in range(50):
        messages.append(
            event(
                f"0x{i:064x}",
                hex(i),
                hex(100 + i),
            )
        )

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        max_seen=10,
        connect_factory=FakeFactory([
            FakeWebSocket(
                messages
            )
        ]),
    )

    result = run(
        runtime.run(
            max_events=50
        )
    )

    assert result[
        "seen_size"
    ] == 10

    assert result[
        "bounded_seen"
    ] is True


def test_malformed_message_is_rejected():
    ws = FakeWebSocket([
        ack(),
        {
            "jsonrpc": "2.0",
            "method": "something_else",
        },
        event(
            "0xaaa",
            "0x1",
            "0x10",
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

    assert result[
        "rejected_count"
    ] == 1

    assert result[
        "accepted_count"
    ] == 1


def test_callback_receives_only_accepted():
    received = []

    async def callback(
        event_row,
    ):
        received.append(
            event_row[
                "event_identity"
            ]
        )

    duplicate = event(
        "0xaaa",
        "0x1",
        "0x10",
    )

    ws = FakeWebSocket([
        ack(),
        duplicate,
        duplicate,
        event(
            "0xbbb",
            "0x2",
            "0x10",
        ),
    ])

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([
            ws
        ]),
        on_event=callback,
    )

    run(
        runtime.run(
            max_events=2
        )
    )

    assert received == [
        "0xaaa:0x1",
        "0xbbb:0x2",
    ]


def test_authority_zero():
    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=FakeFactory([]),
    )

    r = runtime.status()

    assert r[
        "decision_authority"
    ] is False

    assert r[
        "paper_authority"
    ] is False

    assert r[
        "live_authority"
    ] is False

    assert r[
        "wallet_authority"
    ] is False

    assert r[
        "execution_authority"
    ] is False
