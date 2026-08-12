import asyncio
import json
from collections import deque

from app.dex.native_ingestion import SWAP_TOPIC
from app.dex.wss_runtime import NativeWSSRuntime
from app.pipeline.intelligence_composition import (
    RuntimeIntelligenceComposition,
)


def _event(
    tx,
    idx,
    block,
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
                "topics": [SWAP_TOPIC],
            },
        },
    }


def _ack(subscription="sub-1"):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": subscription,
    }


class FakeWS:
    def __init__(self, rows):
        self.rows = deque(rows)
        self.sent = []

    async def send(self, payload):
        self.sent.append(
            json.loads(payload)
        )

    async def recv(self):
        if not self.rows:
            raise ConnectionError(
                "stream exhausted"
            )

        row = self.rows.popleft()

        if isinstance(
            row,
            BaseException,
        ):
            raise row

        return json.dumps(row)

    async def close(self):
        pass


class CM:
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
        await self.ws.close()


class Factory:
    def __init__(self, sockets):
        self.sockets = deque(
            sockets
        )
        self.calls = 0

    def __call__(
        self,
        url,
        **kwargs,
    ):
        self.calls += 1

        if not self.sockets:
            raise ConnectionError(
                "no provider"
            )

        return CM(
            self.sockets.popleft()
        )


def test_wss_to_composition_observation_chain():
    composition = (
        RuntimeIntelligenceComposition()
    )

    accepted = []

    async def on_event(event):
        accepted.append(event)

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=Factory([
            FakeWS([
                _ack(),
                _event(
                    "0xaaa",
                    "0x1",
                    "0x10",
                ),
                _event(
                    "0xbbb",
                    "0x2",
                    "0x10",
                ),
            ])
        ]),
        on_event=on_event,
    )

    result = asyncio.run(
        runtime.run(
            max_events=2
        )
    )

    assert result[
        "accepted_count"
    ] == 2

    assert len(accepted) == 2

    context = composition.build(
        "0xtoken",
        market_input={
            "volume_usd": 20000,
            "buy_volume_usd": 12000,
            "sell_volume_usd": 8000,
            "buyers": 10,
            "sellers": 10,
            "buys": 20,
            "sells": 20,
            "liquidity_usd": 50000,
        },
        flow_input={
            "buy_flow": 120,
            "sell_flow": 80,
            "prev_spread": 20,
            "prev_velocity": 5,
            "direction": "BULL",
            "price_direction": "UP",
            "unique_wallets": 10,
            "tx_count": 20,
            "largest_actor_share": 0.20,
        },
    )

    assert context[
        "runtime_connected"
    ]["phase5_market"] is True

    assert context[
        "runtime_connected"
    ]["phase7_flow_regime"] is True

    assert context[
        "runtime_connected"
    ]["phase8_native_binding"] is True

    assert context[
        "decision_authority"
    ] is False


def test_duplicate_and_removed_never_reach_callback():
    accepted = []

    async def on_event(event):
        accepted.append(
            event["event_identity"]
        )

    duplicate = _event(
        "0xaaa",
        "0x1",
        "0x10",
    )

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=Factory([
            FakeWS([
                _ack(),
                duplicate,
                duplicate,
                _event(
                    "0xremoved",
                    "0x2",
                    "0x10",
                    removed=True,
                ),
                _event(
                    "0xbbb",
                    "0x3",
                    "0x10",
                ),
            ])
        ]),
        on_event=on_event,
    )

    result = asyncio.run(
        runtime.run(
            max_events=2
        )
    )

    assert accepted == [
        "0xaaa:0x1",
        "0xbbb:0x3",
    ]

    assert result[
        "duplicate_count"
    ] == 1

    assert result[
        "removed_count"
    ] == 1


def test_reconnect_preserves_seen_memory():
    first = FakeWS([
        _ack(),
        _event(
            "0xaaa",
            "0x1",
            "0x10",
        ),
        ConnectionError(
            "disconnect"
        ),
    ])

    second = FakeWS([
        _ack("sub-2"),
        _event(
            "0xaaa",
            "0x1",
            "0x10",
            subscription="sub-2",
        ),
        _event(
            "0xbbb",
            "0x2",
            "0x10",
            subscription="sub-2",
        ),
    ])

    async def no_sleep(_):
        pass

    runtime = NativeWSSRuntime(
        "wss://example",
        "0xpair",
        connect_factory=Factory([
            first,
            second,
        ]),
        sleep_func=no_sleep,
        max_reconnects=2,
    )

    result = asyncio.run(
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

    assert result[
        "reconnect_count"
    ] == 1


def test_readmodels_cannot_upgrade_candidate():
    c = RuntimeIntelligenceComposition()

    c.update_wallet(
        "bsc:0xabc",
        {
            "wallet_context_ready": True,
            "market_context_allowed": True,
            "wallet_id": "bsc:0xabc",
            "wallet_hard_risk": False,
        },
    )

    c.update_adversary(
        "actor:1",
        {
            "state": "LOW_RISK",
            "risk_score": 0,
            "hard_evidence": False,
            "evidence_tags": [],
        },
    )

    r = c.build(
        "0xtoken",
        wallet_id="bsc:0xabc",
        adversary_key="actor:1",
    )

    assert r[
        "can_upgrade_candidate"
    ] is False

    assert r[
        "trade_permission"
    ] is False

    assert r[
        "execution_authority"
    ] is False
