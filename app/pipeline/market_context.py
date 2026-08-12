def _positive_number(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if value < 0:
        return None

    return value


def build_market_context(
    row,
    runtime_feed=None,
):
    """
    Candidate execution evidence + operational intelligence.

    Scanner evidence is real candidate/source evidence.
    Native flow evidence is used only when runtime_feed has
    real registered-pair WSS observations.

    Missing evidence stays UNKNOWN/absent.
    No fake price impact, slippage, sell-flow or USD side-volume.
    """

    row = row or {}

    context = {
        "liquidity_usd": (
            _positive_number(
                row.get("liquidity")
            )
        ),
        "trade_size_usd": (
            _positive_number(
                row.get(
                    "trade_size_usd"
                )
            )
        ),
        "price_impact_pct": (
            _positive_number(
                row.get(
                    "price_impact_pct"
                )
            )
        ),
        "slippage_pct": (
            _positive_number(
                row.get(
                    "slippage_pct"
                )
            )
        ),
    }

    if runtime_feed is None:
        return context

    snapshot = runtime_feed.snapshot(
        row.get("pool"),
        candidate=row,
    )

    context[
        "runtime_market_flow"
    ] = snapshot

    market = snapshot.get(
        "market_intelligence"
    ) or {}

    flow = snapshot.get(
        "flow_intelligence"
    ) or {}

    if market.get(
        "evidence_ready"
    ):
        context[
            "market_intelligence"
        ] = market

    if flow.get(
        "evidence_ready"
    ):
        context[
            "flow_intelligence"
        ] = flow

    return context
