import math


def _number(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value) or value < 0:
        return None

    return value


def _integer(value):
    if value is None:
        return None

    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    if value < 0:
        return None

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
    previous_liquidity_usd = _number(previous_liquidity_usd)

    transaction_evidence_ready = (
        buys is not None
        and sells is not None
    )

    participant_evidence_ready = (
        buyers is not None
        and sellers is not None
    )

    side_volume_evidence_ready = (
        buy_volume_usd is not None
        and sell_volume_usd is not None
    )

    transaction_count = (
        buys + sells
        if transaction_evidence_ready
        else None
    )

    unique_participants = (
        buyers + sellers
        if participant_evidence_ready
        else None
    )

    transaction_participation_ratio = None

    if (
        transaction_count is not None
        and transaction_count > 0
        and unique_participants is not None
    ):
        transaction_participation_ratio = (
            unique_participants
            / transaction_count
        )

    buy_sell_count_ratio = None

    if transaction_evidence_ready:
        if sells > 0:
            buy_sell_count_ratio = buys / sells
        elif buys > 0:
            buy_sell_count_ratio = float(buys)
        else:
            buy_sell_count_ratio = 0.0

    buyer_seller_ratio = None

    if participant_evidence_ready:
        if sellers > 0:
            buyer_seller_ratio = buyers / sellers
        elif buyers > 0:
            buyer_seller_ratio = float(buyers)
        else:
            buyer_seller_ratio = 0.0

    volume_turnover = None

    if (
        volume_usd is not None
        and liquidity_usd is not None
        and liquidity_usd > 0
    ):
        volume_turnover = volume_usd / liquidity_usd

    side_volume_coverage = None

    if (
        side_volume_evidence_ready
        and volume_usd is not None
        and volume_usd > 0
    ):
        side_volume_coverage = (
            buy_volume_usd + sell_volume_usd
        ) / volume_usd

    liquidity_change_pct = None

    if (
        liquidity_usd is not None
        and previous_liquidity_usd is not None
        and previous_liquidity_usd > 0
    ):
        liquidity_change_pct = (
            liquidity_usd - previous_liquidity_usd
        ) / previous_liquidity_usd

    if transaction_count is None:
        participation_state = "UNKNOWN"
    elif transaction_count == 0:
        participation_state = "NO_FLOW"
    elif unique_participants is None:
        participation_state = "UNKNOWN"
    elif unique_participants <= 1:
        participation_state = "CONCENTRATED"
    elif (
        transaction_participation_ratio is not None
        and transaction_participation_ratio < 0.25
    ):
        participation_state = "LOW_DIVERSITY"
    else:
        participation_state = "DIVERSE"

    if liquidity_usd is None:
        liquidity_state = "UNKNOWN"
    elif liquidity_usd <= 0:
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
    elif liquidity_change_pct == 0:
        liquidity_state = "STABLE"
    else:
        liquidity_state = "STABLE_OR_UNKNOWN"

    market_evidence_ready = (
        transaction_evidence_ready
        and participant_evidence_ready
        and liquidity_usd is not None
    )

    suspicious_volume = None

    if (
        volume_usd is not None
        and volume_usd > 0
        and transaction_count is not None
        and transaction_count > 0
        and unique_participants is not None
    ):
        suspicious_volume = unique_participants <= 1

    return {
        "volume_usd": volume_usd,
        "buy_volume_usd": buy_volume_usd,
        "sell_volume_usd": sell_volume_usd,
        "buyers": buyers,
        "sellers": sellers,
        "buys": buys,
        "sells": sells,
        "unique_participants": unique_participants,
        "transaction_count": transaction_count,
        "transaction_participation_ratio": transaction_participation_ratio,
        "buy_sell_count_ratio": buy_sell_count_ratio,
        "buyer_seller_ratio": buyer_seller_ratio,
        "volume_turnover": volume_turnover,
        "side_volume_coverage": side_volume_coverage,
        "liquidity_usd": liquidity_usd,
        "liquidity_change_pct": liquidity_change_pct,
        "participation_state": participation_state,
        "liquidity_state": liquidity_state,
        "suspicious_volume": suspicious_volume,
        "market_evidence_ready": market_evidence_ready,
        "transaction_evidence_ready": transaction_evidence_ready,
        "participant_evidence_ready": participant_evidence_ready,
        "side_volume_evidence_ready": side_volume_evidence_ready,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
