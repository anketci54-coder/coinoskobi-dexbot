import asyncio

from app.dex.runtime_actor_intelligence import (
    RuntimeActorIntelligence,
)
from app.dex.transaction_origin import (
    TransactionOriginResolver,
)
from app.pipeline.intelligence_composition import (
    RuntimeIntelligenceComposition,
)


PAIR = (
    "0x00000000000000000000000000000000000000aa"
)

WALLET = (
    "0x0000000000000000000000000000000000000123"
)


def test_real_actor_updates_existing_readmodels():
    intelligence = (
        RuntimeIntelligenceComposition()
    )

    runtime = (
        RuntimeActorIntelligence(
            resolver=(
                TransactionOriginResolver(
                    fetcher=lambda _: {
                        "from": WALLET
                    },
                )
            ),
            wallet_writer=(
                intelligence.update_wallet
            ),
            adversary_writer=(
                intelligence.update_adversary
            ),
        )
    )

    asyncio.run(
        runtime.observe_event(
            {
                "event_identity": (
                    "0xaaa:0x1"
                ),
                "transaction_hash": (
                    "0xaaa"
                ),
                "address": PAIR,
                "block_number": "0x10",
                "log_index": "0x1",
            },
            direction="BULL",
        )
    )

    wallet_id = (
        f"bsc:{WALLET}"
    )

    result = intelligence.build(
        "0xtoken",
        wallet_id=wallet_id,
        adversary_key=wallet_id,
    )

    assert result[
        "wallet_readmodel"
    ][
        "state"
    ] == "READY"

    assert result[
        "adversary_readmodel"
    ][
        "state"
    ] == "READY"

    assert result[
        "wallet_readmodel"
    ][
        "payload"
    ][
        "identity_source"
    ] == "TRANSACTION_FROM_ONLY"

    assert result[
        "adversary_bridge"
    ][
        "wallet_context_ready"
    ] is True

    assert result[
        "adversary_bridge"
    ][
        "can_upgrade_candidate"
    ] is False

    assert result[
        "execution_authority"
    ] is False
