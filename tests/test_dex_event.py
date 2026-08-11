import pytest

from app.dex.event import normalize_event


def test_normalized_event_contract():
    event = normalize_event(
        chain="BSC",
        chain_id=56,
        dex="PancakeSwap_V2",
        event_type="swap",
        block_number=100,
        tx_hash="0xABC",
        log_index=2,
        pool="0xPAIR",
        observed_at=1.25,
        data={"side": "BUY"},
    )

    assert event.chain == "bsc"
    assert event.chain_id == 56
    assert event.dex == "pancakeswap_v2"
    assert event.event_type == "SWAP"
    assert event.pool == "0xpair"
    assert event.identity == (
        "bsc",
        "0xabc",
        2,
    )


def test_negative_block_rejected():
    with pytest.raises(ValueError):
        normalize_event(
            chain="bsc",
            chain_id=56,
            dex="pancakeswap_v2",
            event_type="swap",
            block_number=-1,
            tx_hash="0x1",
            log_index=0,
            pool="0x2",
            observed_at=0,
        )
