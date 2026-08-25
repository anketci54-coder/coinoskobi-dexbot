from collections import Counter

from app.dex.transaction_origin import (
    resolved_transaction_origin,
)


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


def _origin_participation(runtime_feed, pair):
    """
    Build participant evidence only from already-resolved transaction.from.

    Direction remains native Swap amount evidence. Identity never falls
    back to the Pair Swap sender. Partial identity coverage stays UNKNOWN.
    """
    pair_key = str(pair or "").strip().lower()

    if not pair_key or runtime_feed is None:
        return {
            "state": "UNKNOWN",
            "coverage": 0.0,
        }

    event_store = getattr(
        runtime_feed,
        "_events",
        None,
    )

    if not isinstance(event_store, dict):
        return {
            "state": "UNKNOWN",
            "coverage": 0.0,
        }

    events = event_store.get(pair_key)

    if not events:
        return {
            "state": "UNKNOWN",
            "coverage": 0.0,
        }

    directional = [
        row
        for row in events.values()
        if row.get("direction")
        in {"BULL", "BEAR"}
    ]

    if not directional:
        return {
            "state": "UNKNOWN",
            "coverage": 0.0,
        }

    resolved = []

    for row in directional:
        tx_hash = row.get(
            "transaction_hash"
        )
        origin = resolved_transaction_origin(
            tx_hash
        )

        if origin:
            resolved.append((row, origin))

    coverage = len(resolved) / len(directional)

    if coverage < 1.0:
        return {
            "state": "UNKNOWN",
            "coverage": coverage,
            "resolved_events": len(resolved),
            "directional_events": len(directional),
            "identity_source": "TRANSACTION_FROM_ONLY",
            "swap_sender_is_wallet": False,
        }

    buyers = {
        origin
        for row, origin in resolved
        if row.get("direction") == "BULL"
    }

    sellers = {
        origin
        for row, origin in resolved
        if row.get("direction") == "BEAR"
    }

    actor_counts = Counter(
        origin
        for _, origin in resolved
    )

    total = len(resolved)

    largest_actor_share = (
        max(actor_counts.values()) / total
        if actor_counts and total > 0
        else None
    )

    return {
        "state": "READY",
        "coverage": coverage,
        "buyers": len(buyers),
        "sellers": len(sellers),
        "unique_wallets": len(actor_counts),
        "tx_count": total,
        "largest_actor_share": largest_actor_share,
        "identity_source": "TRANSACTION_FROM_ONLY",
        "swap_sender_is_wallet": False,
    }


def _bind_origin_participation(
    *,
    runtime_feed,
    pair,
    market,
    flow,
):
    participant = _origin_participation(
        runtime_feed,
        pair,
    )

    market = dict(market or {})
    flow = dict(flow or {})

    if participant.get("state") == "READY":
        market["buyers"] = participant["buyers"]
        market["sellers"] = participant["sellers"]
        market["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        market["participant_identity_coverage"] = (
            participant["coverage"]
        )

        flow["unique_wallets"] = (
            participant["unique_wallets"]
        )
        flow["tx_count"] = participant["tx_count"]
        flow["largest_actor_share"] = (
            participant["largest_actor_share"]
        )
        flow["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        flow["participant_identity_coverage"] = (
            participant["coverage"]
        )

    else:
        # Sender-derived participant counts are not wallet evidence.
        # Remove them instead of falling back or guessing.
        market.pop("buyers", None)
        market.pop("sellers", None)
        flow.pop("unique_wallets", None)
        flow.pop("largest_actor_share", None)

        market["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        market["participant_identity_coverage"] = (
            participant.get("coverage", 0.0)
        )
        flow["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        flow["participant_identity_coverage"] = (
            participant.get("coverage", 0.0)
        )

    return market, flow, participant


def build_market_context(
    row,
    runtime_feed=None,
):
    """
    Candidate execution evidence + operational intelligence.

    Scanner evidence is real candidate/source evidence.
    Native flow direction/count is real WSS evidence.
    Participant identity is accepted only from resolved transaction.from.
    Missing evidence stays UNKNOWN/absent.
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

    market = dict(
        snapshot.get(
            "market_intelligence"
        )
        or {}
    )

    flow = dict(
        snapshot.get(
            "flow_intelligence"
        )
        or {}
    )

    market, flow, participation = (
        _bind_origin_participation(
            runtime_feed=runtime_feed,
            pair=row.get("pool"),
            market=market,
            flow=flow,
        )
    )

    snapshot[
        "market_intelligence"
    ] = market
    snapshot[
        "flow_intelligence"
    ] = flow
    snapshot[
        "origin_participation"
    ] = participation

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

    context[
        "origin_participation"
    ] = participation

    return context
