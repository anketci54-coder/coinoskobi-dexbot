import asyncio

from app.dex.runtime_actor_intelligence import (
    RuntimeActorIntelligence,
)
from app.dex.transaction_origin import (
    forget_transaction_origin,
    remember_transaction_origin,
    resolved_transaction_origin,
)

PAIR = "0x0000000000000000000000000000000000000101"
TX = "0x" + "12" * 32
WALLET = "0x0000000000000000000000000000000000000202"


class DeferredResolver:
    async def resolve(self, tx_hash):
        address = resolved_transaction_origin(tx_hash)
        if address:
            return {
                "state": "READY",
                "transaction_hash": tx_hash,
                "address": address,
                "source": "CACHE",
            }
        return {
            "state": "UNKNOWN",
            "transaction_hash": tx_hash,
            "address": None,
            "source": "PROVIDER_LOOKUP_PENDING",
        }

    def forget(self, tx_hash):
        return forget_transaction_origin(tx_hash)

    def status(self):
        return {
            "state": "READY",
            "provider_calls": 0,
            "resolve_failures": 0,
        }


def event(identity="evt-1"):
    return {
        "address": PAIR,
        "event_identity": identity,
        "transaction_hash": TX,
        "block_number": 1,
        "log_index": 1,
    }


def test_unresolved_event_replays_after_origin_bridge_ready():
    async def scenario():
        forget_transaction_origin(TX)

        actor = RuntimeActorIntelligence(
            resolver=DeferredResolver(),
            origin_replay_timeout_seconds=0.5,
            origin_replay_poll_seconds=0.01,
        )

        first = await actor.observe_event(
            event(),
            direction="BULL",
        )

        assert first["state"] == "UNKNOWN"
        assert actor.status()["pending_origin_replays"] == 1

        remember_transaction_origin(
            TX,
            WALLET,
        )

        await asyncio.sleep(0.08)

        status = actor.status()

        assert status["accepted_events"] == 1
        assert status["origin_replay_accepted"] == 1
        assert status["pending_origin_replays"] == 0
        assert actor.snapshot(PAIR)["state"] == "READY"

        forget_transaction_origin(TX)

    asyncio.run(scenario())


def test_origin_replay_does_not_make_provider_call():
    async def scenario():
        forget_transaction_origin(TX)

        resolver = DeferredResolver()

        actor = RuntimeActorIntelligence(
            resolver=resolver,
            origin_replay_timeout_seconds=0.5,
            origin_replay_poll_seconds=0.01,
        )

        await actor.observe_event(
            event(),
            direction="BEAR",
        )

        remember_transaction_origin(
            TX,
            WALLET,
        )

        await asyncio.sleep(0.08)

        assert resolver.status()["provider_calls"] == 0
        assert actor.status()["origin_replay_accepted"] == 1

        forget_transaction_origin(TX)

    asyncio.run(scenario())


def test_retraction_cancels_pending_origin_replay():
    async def scenario():
        forget_transaction_origin(TX)

        actor = RuntimeActorIntelligence(
            resolver=DeferredResolver(),
            origin_replay_timeout_seconds=0.5,
            origin_replay_poll_seconds=0.01,
        )

        await actor.observe_event(
            event(),
            direction="BULL",
        )

        result = await actor.observe_retraction({
            "address": PAIR,
            "retracts_event_identity": "evt-1",
            "transaction_hash": TX,
        })

        assert result["state"] == "IGNORED"

        await asyncio.sleep(0)

        status = actor.status()
        assert status["pending_origin_replays"] == 0
        assert status["accepted_events"] == 0

        forget_transaction_origin(TX)

    asyncio.run(scenario())
