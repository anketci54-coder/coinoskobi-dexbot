from app.dex.event import normalize_event
from app.dex.market_clock import MarketClock


def event(index, observed_at, block, event_type="SWAP"):
    return normalize_event(
        chain="bsc",
        chain_id=56,
        dex="pancakeswap_v2",
        event_type=event_type,
        block_number=block,
        tx_hash=f"0x{index:064x}",
        log_index=index,
        pool="0xpool",
        observed_at=observed_at,
        data={},
    )


def test_wall_clock_window():
    clock = MarketClock()

    clock.add(event(1, 9.0, 100))
    clock.add(event(2, 9.8, 101))
    clock.add(event(3, 10.0, 101))

    result = clock.wall_window(
        now=10.0,
        seconds=0.5,
    )

    assert len(result) == 2


def test_block_clock_window():
    clock = MarketClock()

    for i, block in enumerate(
        (100, 101, 102, 103),
        start=1,
    ):
        clock.add(
            event(i, float(i), block)
        )

    result = clock.block_window(
        latest_block=103,
        block_count=2,
    )

    assert [
        row.block_number
        for row in result
    ] == [102, 103]


def test_swap_clock_window():
    clock = MarketClock()

    for i in range(10):
        clock.add(
            event(
                i,
                float(i),
                100 + i,
            )
        )

    assert len(
        clock.swap_window(5)
    ) == 5
