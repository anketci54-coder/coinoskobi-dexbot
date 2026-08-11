def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def analyze_swap_flow(events):
    swaps = [
        event
        for event in events
        if event.event_type == "SWAP"
    ]

    buy_count = 0
    sell_count = 0

    buy_volume = 0.0
    sell_volume = 0.0

    for event in swaps:
        data = event.data or {}

        side = str(
            data.get("side") or ""
        ).strip().upper()

        amount_usd = _number(
            data.get("amount_usd")
        )

        if side == "BUY":
            buy_count += 1
            buy_volume += amount_usd

        elif side == "SELL":
            sell_count += 1
            sell_volume += amount_usd

    total_count = (
        buy_count
        + sell_count
    )

    total_volume = (
        buy_volume
        + sell_volume
    )

    count_imbalance = (
        (buy_count - sell_count)
        / total_count
        if total_count
        else 0.0
    )

    volume_imbalance = (
        (buy_volume - sell_volume)
        / total_volume
        if total_volume
        else 0.0
    )

    return {
        "swap_count": total_count,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "buy_volume_usd": buy_volume,
        "sell_volume_usd": sell_volume,
        "count_imbalance": count_imbalance,
        "volume_imbalance": volume_imbalance,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
