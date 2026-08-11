from app.dex.event import normalize_event
from app.dex.swap_flow import analyze_swap_flow


def swap(index, side, amount):
    return normalize_event(
        chain="bsc",
        chain_id=56,
        dex="pancakeswap_v2",
        event_type="SWAP",
        block_number=100 + index,
        tx_hash=f"0x{index:064x}",
        log_index=index,
        pool="0xpool",
        observed_at=float(index),
        data={
            "side": side,
            "amount_usd": amount,
        },
    )


def test_buy_dominant_flow():
    result = analyze_swap_flow([
        swap(1, "BUY", 100),
        swap(2, "BUY", 200),
        swap(3, "SELL", 50),
    ])

    assert result["swap_count"] == 3
    assert result["buy_count"] == 2
    assert result["sell_count"] == 1
    assert result["buy_volume_usd"] == 300
    assert result["sell_volume_usd"] == 50
    assert result["count_imbalance"] > 0
    assert result["volume_imbalance"] > 0


def test_empty_flow_is_neutral():
    result = analyze_swap_flow([])

    assert result["swap_count"] == 0
    assert result["count_imbalance"] == 0
    assert result["volume_imbalance"] == 0


def test_swap_flow_has_no_trade_authority():
    result = analyze_swap_flow([
        swap(1, "BUY", 1000),
    ])

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
