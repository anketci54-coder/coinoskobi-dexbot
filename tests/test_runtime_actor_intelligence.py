import asyncio

from app.dex.runtime_actor_intelligence import (
    RuntimeActorIntelligence,
)
from app.dex.transaction_origin import (
    TransactionOriginResolver,
)


PAIR = (
    "0x00000000000000000000000000000000000000aa"
)

WALLET_A = (
    "0x0000000000000000000000000000000000000101"
)

WALLET_B = (
    "0x0000000000000000000000000000000000000202"
)

ROUTER = (
    "0x0000000000000000000000000000000000009999"
)


def run(value):
    return asyncio.run(value)


def event(
    identity,
    tx_hash,
):
    return {
        "event_identity": identity,
        "transaction_hash": tx_hash,
        "address": PAIR,
        "block_number": "0x10",
        "log_index": "0x1",
        "topics": [
            "0xtopic",
            ROUTER,
        ],
    }


def test_real_tx_from_not_swap_sender_becomes_wallet():
    wallet_rows = {}
    adversary_rows = {}

    resolver = (
        TransactionOriginResolver(
            fetcher=lambda _: {
                "from": WALLET_A
            },
        )
    )

    runtime = (
        RuntimeActorIntelligence(
            resolver=resolver,
            wallet_writer=lambda k, v: (
                wallet_rows.__setitem__(
                    k,
                    v,
                )
            ),
            adversary_writer=lambda k, v: (
                adversary_rows.__setitem__(
                    k,
                    v,
                )
            ),
        )
    )

    result = run(
        runtime.observe_event(
            event(
                "0xaaa:0x1",
                "0xaaa",
            ),
            direction="BULL",
        )
    )

    wallet_id = (
        f"bsc:{WALLET_A}"
    )

    assert result[
        "wallet_id"
    ] == wallet_id

    assert (
        f"bsc:{ROUTER}"
        not in wallet_rows
    )

    assert wallet_id in wallet_rows
    assert wallet_id in adversary_rows

    wallet = wallet_rows[
        wallet_id
    ]

    assert wallet[
        "identity_source"
    ] == "TRANSACTION_FROM_ONLY"

    assert wallet[
        "identity_guessing"
    ] is False

    assert wallet[
        "swap_sender_is_wallet"
    ] is False

    assert wallet[
        "buy_count"
    ] == 1

    assert wallet[
        "sell_count"
    ] == 0


def test_entity_scope_is_self_only():
    wallet_rows = {}

    resolver = (
        TransactionOriginResolver(
            fetcher=lambda _: {
                "from": WALLET_A
            },
        )
    )

    runtime = (
        RuntimeActorIntelligence(
            resolver=resolver,
            wallet_writer=lambda k, v: (
                wallet_rows.__setitem__(
                    k,
                    v,
                )
            ),
        )
    )

    run(
        runtime.observe_event(
            event(
                "0xaaa:0x1",
                "0xaaa",
            ),
            direction="BULL",
        )
    )

    wallet = wallet_rows[
        f"bsc:{WALLET_A}"
    ]

    assert (
        wallet[
            "entity_scope"
        ]
        == "SELF_ONLY_NO_CROSS_WALLET_MERGE"
    )

    assert wallet[
        "entity_auto_merge"
    ] is False

    assert wallet[
        "entity_identity_proof"
    ] is False


def test_small_sample_does_not_create_hard_risk():
    adversary_rows = {}

    resolver = (
        TransactionOriginResolver(
            fetcher=lambda _: {
                "from": WALLET_A
            },
        )
    )

    runtime = (
        RuntimeActorIntelligence(
            resolver=resolver,
            adversary_writer=lambda k, v: (
                adversary_rows.__setitem__(
                    k,
                    v,
                )
            ),
        )
    )

    run(
        runtime.observe_event(
            event(
                "0xaaa:0x1",
                "0xaaa",
            ),
            direction="BULL",
        )
    )

    adv = adversary_rows[
        f"bsc:{WALLET_A}"
    ]

    assert adv[
        "hard_evidence"
    ] is False

    assert adv[
        "state"
    ] in {
        "LOW_RISK",
        "WATCH",
    }


def test_provider_failure_does_not_write_identity():
    wallets = {}

    def fetcher(_):
        raise TimeoutError()

    runtime = (
        RuntimeActorIntelligence(
            resolver=(
                TransactionOriginResolver(
                    fetcher=fetcher
                )
            ),
            wallet_writer=lambda k, v: (
                wallets.__setitem__(
                    k,
                    v,
                )
            ),
        )
    )

    result = run(
        runtime.observe_event(
            event(
                "0xaaa:0x1",
                "0xaaa",
            ),
            direction="BULL",
        )
    )

    assert result[
        "state"
    ] == "UNKNOWN"

    assert wallets == {}

    assert runtime.status()[
        "unresolved_origins"
    ] == 1


def test_retraction_rewrites_last_actor_safe():
    wallet_rows = {}
    adversary_rows = {}

    resolver = (
        TransactionOriginResolver(
            fetcher=lambda _: {
                "from": WALLET_A
            },
        )
    )

    runtime = (
        RuntimeActorIntelligence(
            resolver=resolver,
            wallet_writer=lambda k, v: (
                wallet_rows.__setitem__(
                    k,
                    v,
                )
            ),
            adversary_writer=lambda k, v: (
                adversary_rows.__setitem__(
                    k,
                    v,
                )
            ),
        )
    )

    row = event(
        "0xaaa:0x1",
        "0xaaa",
    )

    run(
        runtime.observe_event(
            row,
            direction="BULL",
        )
    )

    retract = dict(row)

    retract[
        "retracts_event_identity"
    ] = "0xaaa:0x1"

    result = run(
        runtime.observe_retraction(
            retract
        )
    )

    wallet_id = (
        f"bsc:{WALLET_A}"
    )

    assert result[
        "state"
    ] == "RETRACTED"

    assert wallet_rows[
        wallet_id
    ][
        "wallet_context_ready"
    ] is False

    assert adversary_rows[
        wallet_id
    ][
        "state"
    ] == "UNKNOWN"

    assert runtime.snapshot(
        PAIR
    )[
        "state"
    ] == "UNKNOWN"


def test_pair_event_store_is_bounded():
    def fetcher(tx_hash):
        return {
            "from": WALLET_A
        }

    runtime = (
        RuntimeActorIntelligence(
            max_pairs=4,
            max_events_per_pair=64,
            resolver=(
                TransactionOriginResolver(
                    max_entries=128,
                    fetcher=fetcher,
                )
            ),
        )
    )

    for i in range(1000):
        run(
            runtime.observe_event(
                event(
                    f"0x{i:x}:0x1",
                    f"0x{i:x}",
                ),
                direction=(
                    "BULL"
                    if i % 2 == 0
                    else "BEAR"
                ),
            )
        )

    status = runtime.status()

    assert status[
        "event_count"
    ] == 64

    assert status[
        "bounded"
    ] is True

    assert status[
        "dropped_events"
    ] > 0

    assert status[
        "resolver"
    ][
        "size"
    ] <= 128


def test_latest_real_actor_snapshot():
    origins = {
        "0x1": WALLET_A,
        "0x2": WALLET_B,
    }

    runtime = (
        RuntimeActorIntelligence(
            resolver=(
                TransactionOriginResolver(
                    fetcher=lambda tx: {
                        "from": origins[
                            tx
                        ]
                    },
                )
            ),
        )
    )

    run(
        runtime.observe_event(
            event(
                "0x1:0x1",
                "0x1",
            ),
            direction="BULL",
        )
    )

    run(
        runtime.observe_event(
            event(
                "0x2:0x1",
                "0x2",
            ),
            direction="BEAR",
        )
    )

    snapshot = runtime.snapshot(
        PAIR
    )

    assert snapshot[
        "state"
    ] == "READY"

    assert snapshot[
        "wallet_id"
    ] == f"bsc:{WALLET_B}"

    assert snapshot[
        "adversary_key"
    ] == f"bsc:{WALLET_B}"
