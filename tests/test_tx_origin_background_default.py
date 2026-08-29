import asyncio
import time

from app.dex.transaction_origin import (
    TransactionOriginResolver,
    resolved_transaction_origin,
)


WALLET = "0x0000000000000000000000000000000000000123"


def test_default_provider_lookup_does_not_block_hot_path():
    calls = 0

    def fetcher(_):
        nonlocal calls
        calls += 1
        time.sleep(0.15)
        return {"from": WALLET}

    resolver = TransactionOriginResolver(
        timeout_seconds=0.5,
        negative_ttl_seconds=0.01,
        retry_delay_seconds=0.03,
        max_pending_retries=4,
    )
    resolver.fetcher = fetcher

    async def scenario():
        started = time.monotonic()
        result = await resolver.resolve("0xbackground-fast")
        elapsed = time.monotonic() - started

        assert result["state"] == "UNKNOWN"
        assert result["source"] == "PROVIDER_LOOKUP_PENDING"
        assert elapsed < 0.05

        await asyncio.sleep(0.25)

        assert resolved_transaction_origin(
            "0xbackground-fast"
        ) == WALLET
        assert calls == 1

        status = resolver.status()
        assert status["background_scheduled"] == 1
        assert status["pending_background_lookups"] == 0
        assert status["default_provider_background"] is True

    try:
        asyncio.run(scenario())
    finally:
        resolver.forget("0xbackground-fast")


def test_default_provider_background_lookup_retries_once_after_miss():
    calls = 0

    def fetcher(_):
        nonlocal calls
        calls += 1

        if calls == 1:
            raise TimeoutError("transient")

        return {"from": WALLET}

    resolver = TransactionOriginResolver(
        timeout_seconds=0.2,
        negative_ttl_seconds=0.01,
        retry_delay_seconds=0.03,
        max_pending_retries=4,
    )
    resolver.fetcher = fetcher

    async def scenario():
        first = await resolver.resolve("0xbackground-retry")

        assert first["state"] == "UNKNOWN"
        assert first["source"] == "PROVIDER_LOOKUP_PENDING"
        assert resolved_transaction_origin(
            "0xbackground-retry"
        ) is None

        await asyncio.sleep(0.12)

        assert resolved_transaction_origin(
            "0xbackground-retry"
        ) == WALLET
        assert calls == 2

        status = resolver.status()
        assert status["background_scheduled"] == 1
        assert status["retry_scheduled"] == 1
        assert status["retry_attempts"] == 1
        assert status["retry_successes"] == 1
        assert status["retry_failures"] == 0
        assert status["pending_background_lookups"] == 0

    try:
        asyncio.run(scenario())
    finally:
        resolver.forget("0xbackground-retry")
