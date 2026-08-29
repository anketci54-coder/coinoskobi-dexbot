import asyncio

import app.pipeline.market_context as market_context_module
from app.dex.transaction_origin import (
    TransactionOriginResolver,
)
from app.pipeline.market_context import (
    _bind_origin_participation,
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


def test_partial_origin_coverage_keeps_resolved_wallets_as_lower_bounds(monkeypatch):
    tx1 = "0xpartial-1"
    tx2 = "0xpartial-2"

    class Feed:
        _events = {
            PAIR: {
                "event-1": {
                    "direction": "BULL",
                    "transaction_hash": tx1,
                },
                "event-2": {
                    "direction": "BEAR",
                    "transaction_hash": tx2,
                },
            },
        }

    monkeypatch.setattr(
        market_context_module,
        "resolved_transaction_origin",
        lambda tx_hash: WALLET if tx_hash == tx1 else None,
    )

    result = _origin_participation(Feed(), PAIR)

    assert result["state"] == "PARTIAL"
    assert result["coverage"] == 0.5
    assert result["buyers"] == 1
    assert result["sellers"] == 0
    assert result["unique_wallets"] == 1
    assert result["resolved_events"] == 1
    assert result["unresolved_events"] == 1
    assert result["directional_events"] == 2
    assert result["identity_complete"] is False
    assert result["counts_are_lower_bounds"] is True
    assert result["identity_source"] == "TRANSACTION_FROM_ONLY"
    assert result["swap_sender_is_wallet"] is False


def test_partial_origin_binding_preserves_native_flow_count(monkeypatch):
    tx1 = "0xpartial-bind-1"
    tx2 = "0xpartial-bind-2"

    class Feed:
        _events = {
            PAIR: {
                "event-1": {
                    "direction": "BULL",
                    "transaction_hash": tx1,
                },
                "event-2": {
                    "direction": "BEAR",
                    "transaction_hash": tx2,
                },
            },
        }

    monkeypatch.setattr(
        market_context_module,
        "resolved_transaction_origin",
        lambda tx_hash: WALLET if tx_hash == tx1 else None,
    )

    market, flow, participant = _bind_origin_participation(
        runtime_feed=Feed(),
        pair=PAIR,
        market={"buys": 1, "sells": 1},
        flow={"tx_count": 2, "flow_momentum": 0.5},
    )

    assert participant["state"] == "PARTIAL"
    assert market["buyers"] == 1
    assert market["sellers"] == 0
    assert market["participant_identity_coverage"] == 0.5
    assert market["participant_identity_state"] == "PARTIAL"
    assert market["participant_counts_are_lower_bounds"] is True
    assert flow["unique_wallets"] == 1
    assert flow["tx_count"] == 2
    assert flow["resolved_identity_tx_count"] == 1
    assert flow["participant_identity_coverage"] == 0.5
    assert flow["participant_identity_state"] == "PARTIAL"
    assert flow["participant_counts_are_lower_bounds"] is True


def test_zero_origin_coverage_remains_unknown_without_sender_fallback(monkeypatch):
    class Feed:
        _events = {
            PAIR: {
                "event-1": {
                    "direction": "BULL",
                    "transaction_hash": "0xnone-1",
                    "sender": "0x0000000000000000000000000000000000000999",
                },
            },
        }

    monkeypatch.setattr(
        market_context_module,
        "resolved_transaction_origin",
        lambda _tx_hash: None,
    )

    market, flow, participant = _bind_origin_participation(
        runtime_feed=Feed(),
        pair=PAIR,
        market={"buyers": 7, "sellers": 3},
        flow={"unique_wallets": 9, "tx_count": 1},
    )

    assert participant["state"] == "UNKNOWN"
    assert participant["coverage"] == 0.0
    assert "buyers" not in market
    assert "sellers" not in market
    assert "unique_wallets" not in flow
    assert flow["tx_count"] == 1
    assert participant["swap_sender_is_wallet"] is False
