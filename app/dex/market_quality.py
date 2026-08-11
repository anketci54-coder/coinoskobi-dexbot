def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if value < 0:
        return 0.0

    return value


def _integer(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0

    if value < 0:
        return 0

    return value


def analyze_market_quality(
    *,
    volume_usd=0,
    buy_volume_usd=0,
    sell_volume_usd=0,
    buyers=0,
    sellers=0,
    buys=0,
    sells=0,
    liquidity_usd=0,
    previous_liquidity_usd=None,
):
    volume_usd = _number(volume_usd)
    buy_volume_usd = _number(buy_volume_usd)
    sell_volume_usd = _number(sell_volume_usd)

    buyers = _integer(buyers)
    sellers = _integer(sellers)
    buys = _integer(buys)
    sells = _integer(sells)

    liquidity_usd = _number(liquidity_usd)

    total_transactions = buys + sells
    unique_participants = buyers + sellers

    transaction_participation_ratio = (
        unique_participants / total_transactions
        if total_transactions > 0
        else 0.0
    )

    buy_sell_count_ratio = (
        buys / sells
        if sells > 0
        else float(buys)
        if buys > 0
        else 0.0
    )

    buyer_seller_ratio = (
        buyers / sellers
        if sellers > 0
        else float(buyers)
        if buyers > 0
        else 0.0
    )

    volume_turnover = (
        volume_usd / liquidity_usd
        if liquidity_usd > 0
        else 0.0
    )

    known_side_volume = (
        buy_volume_usd
        + sell_volume_usd
    )

    side_volume_coverage = (
        known_side_volume / volume_usd
        if volume_usd > 0
        else 0.0
    )

    liquidity_change_pct = None

    if previous_liquidity_usd is not None:
        previous = _number(
            previous_liquidity_usd
        )

        if previous > 0:
            liquidity_change_pct = (
                (liquidity_usd - previous)
                / previous
            )

    if total_transactions == 0:
        participation_state = "NO_FLOW"

    elif unique_participants <= 1:
        participation_state = "CONCENTRATED"

    elif (
        transaction_participation_ratio
        < 0.25
    ):
        participation_state = "LOW_DIVERSITY"

    else:
        participation_state = "DIVERSE"

    if liquidity_usd <= 0:
        liquidity_state = "NO_LIQUIDITY"

    elif (
        liquidity_change_pct is not None
        and liquidity_change_pct <= -0.25
    ):
        liquidity_state = "DETERIORATING_FAST"

    elif (
        liquidity_change_pct is not None
        and liquidity_change_pct < 0
    ):
        liquidity_state = "DETERIORATING"

    elif (
        liquidity_change_pct is not None
        and liquidity_change_pct > 0
    ):
        liquidity_state = "IMPROVING"

    else:
        liquidity_state = "STABLE_OR_UNKNOWN"

    suspicious_volume = (
        volume_usd > 0
        and total_transactions > 0
        and unique_participants <= 1
    )

    return {
        "volume_usd": volume_usd,
        "buy_volume_usd": buy_volume_usd,
        "sell_volume_usd": sell_volume_usd,

        "buyers": buyers,
        "sellers": sellers,
        "buys": buys,
        "sells": sells,

        "unique_participants": unique_participants,
        "transaction_count": total_transactions,

        "transaction_participation_ratio": (
            transaction_participation_ratio
        ),
        "buy_sell_count_ratio": buy_sell_count_ratio,
        "buyer_seller_ratio": buyer_seller_ratio,

        "volume_turnover": volume_turnover,
        "side_volume_coverage": side_volume_coverage,

        "liquidity_usd": liquidity_usd,
        "liquidity_change_pct": liquidity_change_pct,

        "participation_state": participation_state,
        "liquidity_state": liquidity_state,
        "suspicious_volume": suspicious_volume,

        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
