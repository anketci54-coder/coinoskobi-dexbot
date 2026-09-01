import asyncio

from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.dex.runtime_actor_tracking_composition import RuntimeActorTrackingComposition
from app.dex.transaction_origin import TransactionOriginResolver

PAIR = "0x00000000000000000000000000000000000000aa"
WALLET = "0x0000000000000000000000000000000000000101"


def test_real_transaction_from_reaches_tracking_without_authority():
    actor = RuntimeActorIntelligence(
        resolver=TransactionOriginResolver(fetcher=lambda _: {"from": WALLET})
    )
    runtime = RuntimeActorTrackingComposition(actor=actor)
    event = {
        "event_identity": "0xabc:0x1",
        "transaction_hash": "0xabc",
        "address": PAIR,
    }

    result = asyncio.run(runtime.observe_event(event, direction="BULL"))
    expected = f"bsc:{WALLET}"

    assert result["actor"]["wallet_id"] == expected
    assert result["wallet_tracking"]["wallet_id"] == expected
    assert result["wallet_tracking"]["identity_source"] == "TRANSACTION_FROM_ONLY"
    assert result["wallet_tracking"]["performance"]["state"] == "UNKNOWN"
    assert result["wallet_tracking"]["holdings"]["state"] == "UNKNOWN"
    assert result["decision_authority"] is False
    assert result["execution_authority"] is False


def test_unresolved_origin_never_enters_tracking():
    def fail(_):
        raise TimeoutError()

    actor = RuntimeActorIntelligence(
        resolver=TransactionOriginResolver(fetcher=fail)
    )
    runtime = RuntimeActorTrackingComposition(actor=actor)
    event = {
        "event_identity": "0xabc:0x1",
        "transaction_hash": "0xabc",
        "address": PAIR,
    }

    result = asyncio.run(runtime.observe_event(event, direction="BULL"))

    assert result["actor"]["state"] == "UNKNOWN"
    assert result["wallet_tracking"]["state"] == "UNKNOWN"
    assert result["wallet_tracking"]["wallet_authority"] is False
