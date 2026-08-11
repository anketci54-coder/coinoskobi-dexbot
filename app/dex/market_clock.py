from collections import deque


class MarketClock:
    """
    Short-horizon DEX measurement windows.

    These are observation windows, not waiting periods.
    """

    WALL_WINDOWS_SEC = (
        0.25,
        0.50,
        1.0,
        2.0,
        5.0,
        10.0,
        30.0,
    )

    BLOCK_WINDOWS = (
        1,
        2,
        4,
        8,
        16,
        32,
    )

    SWAP_WINDOWS = (
        5,
        10,
        25,
        50,
        100,
    )

    def __init__(self, max_events=5000):
        self.events = deque(maxlen=max_events)

    def add(self, event):
        self.events.append(event)

    def wall_window(self, now, seconds):
        cutoff = float(now) - float(seconds)

        return [
            event
            for event in self.events
            if event.observed_at >= cutoff
        ]

    def block_window(self, latest_block, block_count):
        minimum = (
            int(latest_block)
            - int(block_count)
            + 1
        )

        return [
            event
            for event in self.events
            if event.block_number >= minimum
        ]

    def swap_window(self, count):
        swaps = [
            event
            for event in self.events
            if event.event_type == "SWAP"
        ]

        return swaps[-int(count):]
