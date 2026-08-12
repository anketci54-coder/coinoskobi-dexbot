import asyncio

from app.dex.transaction_origin import (
    TransactionOriginResolver,
)


WALLET_A = (
    "0x00000000000000000000000000000000000000aa"
)

WALLET_B = (
    "0x00000000000000000000000000000000000000bb"
)


def run(value):
    return asyncio.run(value)


def test_resolves_real_transaction_from():
    calls = []

    def fetcher(tx_hash):
        calls.append(tx_hash)

        return {
            "hash": tx_hash,
            "from": WALLET_A,
        }

    resolver = (
        TransactionOriginResolver(
            fetcher=fetcher
        )
    )

    result = run(
        resolver.resolve(
            "0xABC"
        )
    )

    assert result[
        "state"
    ] == "READY"

    assert result[
        "address"
    ] == WALLET_A

    assert result[
        "identity_guessing"
    ] is False

    assert result[
        "swap_sender_is_wallet"
    ] is False

    assert calls == [
        "0xabc"
    ]


def test_second_lookup_uses_cache():
    calls = 0

    def fetcher(tx_hash):
        nonlocal calls
        calls += 1

        return {
            "from": WALLET_A
        }

    resolver = (
        TransactionOriginResolver(
            fetcher=fetcher
        )
    )

    first = run(
        resolver.resolve(
            "0x1"
        )
    )

    second = run(
        resolver.resolve(
            "0x1"
        )
    )

    assert first[
        "source"
    ] == "PROVIDER"

    assert second[
        "source"
    ] == "CACHE"

    assert calls == 1

    assert resolver.status()[
        "cache_hits"
    ] == 1


def test_failed_lookup_is_unknown_not_good_wallet():
    def fetcher(tx_hash):
        raise TimeoutError(
            "provider timeout"
        )

    resolver = (
        TransactionOriginResolver(
            fetcher=fetcher
        )
    )

    result = run(
        resolver.resolve(
            "0x1"
        )
    )

    assert result[
        "state"
    ] == "UNKNOWN"

    assert result[
        "address"
    ] is None

    assert resolver.size == 0


def test_cache_is_bounded():
    def fetcher(tx_hash):
        suffix = int(
            tx_hash[2:],
            16,
        ) % 255

        return {
            "from": (
                "0x"
                + f"{suffix:040x}"
            )
        }

    resolver = (
        TransactionOriginResolver(
            max_entries=32,
            fetcher=fetcher,
        )
    )

    for i in range(1000):
        run(
            resolver.resolve(
                f"0x{i:x}"
            )
        )

    status = resolver.status()

    assert status[
        "size"
    ] == 32

    assert status[
        "evictions"
    ] > 0

    assert status[
        "bounded"
    ] is True


def test_forget_removes_cached_origin():
    resolver = (
        TransactionOriginResolver(
            fetcher=lambda _: {
                "from": WALLET_B
            },
        )
    )

    run(
        resolver.resolve(
            "0x1"
        )
    )

    assert resolver.size == 1

    assert resolver.forget(
        "0x1"
    ) is True

    assert resolver.size == 0
