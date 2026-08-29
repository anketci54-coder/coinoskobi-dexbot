import asyncio

from app.dex.transaction_origin import (
    TransactionOriginResolver,
)
from app.pipeline.market_context import (
    _origin_participation,
)


PAIR = (
    "0x00000000000000000000000000000000000000aa"
)
WALLET = (
    "0x0000000000000000000000000000000000000123"
)
TX_HASH = "0xretry-participation"


class RuntimeFeed:
    def __init__(self):
        self._events = {
            PAIR: {
                "event-1": {
                    "direction": "BULL",
                    "transaction_hash": TX_HASH,
                },
            },
        }


def test_retry_restores_full_origin_participation_without_relaxing_gate():
    calls = 0

    def fetcher(_):
        nonlocal calls
        calls += 1

        if calls == 1:
            raise TimeoutError(
                "transient provider failure"
            )

        return {
            "from": WALLET,
        }

    resolver = TransactionOriginResolver(
        fetcher=fetcher,
        timeout_seconds=0.20,
        negative_ttl_seconds=0.01,
        retry_delay_seconds=0.03,
        max_pending_retries=4,
    )
    feed = RuntimeFeed()

    async def scenario():
        first = await resolver.resolve(
            TX_HASH
        )

        assert first["state"] == "UNKNOWN"

        before = _origin_participation(
            feed,
            PAIR,
        )
        assert before["state"] == "UNKNOWN"
        assert before["coverage"] == 0.0

        await asyncio.sleep(0.10)

        after = _origin_participation(
            feed,
            PAIR,
        )
        assert after["state"] == "READY"
        assert after["coverage"] == 1.0
        assert after["resolved_events"] == 1
        assert after["directional_events"] == 1
        assert after["buyers"] == 1
        assert after["sellers"] == 0
        assert after["unique_wallets"] == 1
        assert after["tx_count"] == 1
        assert after["identity_source"] == "TRANSACTION_FROM_ONLY"
        assert after["swap_sender_is_wallet"] is False
        assert calls == 2

    try:
        asyncio.run(scenario())
    finally:
        resolver.forget(TX_HASH)
