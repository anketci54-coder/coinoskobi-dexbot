from collections import Counter
from copy import deepcopy
import threading

from app.dex.transaction_origin import (
    resolved_transaction_origin,
)
from app.dex.news_intelligence import (
    DEFAULT_NEWS_EVIDENCE_STORE,
)
from app.pipeline.news_market_context import (
    bind_news_market_context,
)


_CANDIDATE_SNAPSHOT_BRIDGE_LOCK = threading.Lock()


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


def _pair_key(value):
    value = str(value or "").strip().lower()

    if value.startswith("bsc_"):
        value = value[4:]

    return value


def _install_candidate_snapshot_bridge(runtime_feed):
    """
    Make the next same-thread read for a candidate reuse the exact
    native snapshot that build_market_context admitted.

    WSS ingestion keeps running. The bridge is one-shot and thread-local:
    a later lifecycle/scan read is live again. This prevents a single
    candidate evaluation from advancing mutable flow velocity/acceleration
    state twice and recording a different audit snapshot than the plan used.
    """
    if runtime_feed is None:
        return False

    if getattr(
        runtime_feed,
        "_candidate_snapshot_bridge_installed",
        False,
    ):
        return True

    with _CANDIDATE_SNAPSHOT_BRIDGE_LOCK:
        if getattr(
            runtime_feed,
            "_candidate_snapshot_bridge_installed",
            False,
        ):
            return True

        original = getattr(
            runtime_feed,
            "snapshot",
            None,
        )

        if not callable(original):
            return False

        local = threading.local()

        def bridged_snapshot(
            pair,
            candidate=None,
        ):
            pending = getattr(
                local,
                "pending",
                None,
            )

            if (
                isinstance(pending, dict)
                and pending.get("pair")
                == _pair_key(pair)
            ):
                local.pending = None
                return deepcopy(
                    pending["snapshot"]
                )

            return original(
                pair,
                candidate=candidate,
            )

        runtime_feed._candidate_snapshot_bridge_original = (
            original
        )
        runtime_feed._candidate_snapshot_bridge_local = local
        runtime_feed.snapshot = bridged_snapshot
        runtime_feed._candidate_snapshot_bridge_installed = True

    return True


def _live_candidate_snapshot(
    runtime_feed,
    pair,
    candidate,
):
    if not _install_candidate_snapshot_bridge(
        runtime_feed
    ):
        return runtime_feed.snapshot(
            pair,
            candidate=candidate,
        )

    local = runtime_feed._candidate_snapshot_bridge_local

    # A previous non-admitted candidate may have left an unused one-shot
    # snapshot on this worker thread. Never carry it into a new candidate.
    local.pending = None

    return runtime_feed.snapshot(
        pair,
        candidate=candidate,
    )


def _arm_candidate_snapshot(
    runtime_feed,
    pair,
    snapshot,
):
    if not getattr(
        runtime_feed,
        "_candidate_snapshot_bridge_installed",
        False,
    ):
        return False

    if not isinstance(snapshot, dict):
        return False

    local = runtime_feed._candidate_snapshot_bridge_local
    local.pending = {
        "pair": _pair_key(pair),
        "snapshot": deepcopy(snapshot),
    }
    return True


def _origin_participation(runtime_feed, pair):
    """
    Build conservative participant evidence from resolved transaction.from.

    Direction remains native Swap amount evidence. Identity never falls
    back to the Pair Swap sender. Partial coverage is retained as a truthful
    lower bound: unresolved events are never invented as wallets and can only
    increase the true participant count later.
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

    if not resolved:
        return {
            "state": "UNKNOWN",
            "coverage": coverage,
            "resolved_events": 0,
            "unresolved_events": len(directional),
            "directional_events": len(directional),
            "identity_source": "TRANSACTION_FROM_ONLY",
            "identity_complete": False,
            "counts_are_lower_bounds": True,
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

    resolved_total = len(resolved)

    largest_actor_share = (
        max(actor_counts.values()) / resolved_total
        if actor_counts and resolved_total > 0
        else None
    )

    complete = coverage >= 1.0

    return {
        "state": (
            "READY"
            if complete
            else "PARTIAL"
        ),
        "coverage": coverage,
        "buyers": len(buyers),
        "sellers": len(sellers),
        "unique_wallets": len(actor_counts),
        "tx_count": resolved_total,
        "resolved_events": resolved_total,
        "unresolved_events": (
            len(directional) - resolved_total
        ),
        "directional_events": len(directional),
        "largest_actor_share": largest_actor_share,
        "identity_source": "TRANSACTION_FROM_ONLY",
        "identity_complete": complete,
        "counts_are_lower_bounds": not complete,
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

    state = participant.get("state")

    if state in {"READY", "PARTIAL"}:
        # These are resolved transaction.from wallet counts only. Under
        # PARTIAL coverage they are conservative lower bounds; unresolved
        # events are not guessed and are not counted as participants.
        market["buyers"] = participant["buyers"]
        market["sellers"] = participant["sellers"]
        market["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        market["participant_identity_coverage"] = (
            participant["coverage"]
        )
        market["participant_identity_state"] = state
        market["participant_identity_complete"] = (
            participant["identity_complete"]
        )
        market["participant_counts_are_lower_bounds"] = (
            participant["counts_are_lower_bounds"]
        )

        flow["unique_wallets"] = (
            participant["unique_wallets"]
        )
        flow["resolved_identity_tx_count"] = (
            participant["resolved_events"]
        )
        flow["largest_actor_share"] = (
            participant["largest_actor_share"]
        )
        flow["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        flow["participant_identity_coverage"] = (
            participant["coverage"]
        )
        flow["participant_identity_state"] = state
        flow["participant_identity_complete"] = (
            participant["identity_complete"]
        )
        flow["participant_counts_are_lower_bounds"] = (
            participant["counts_are_lower_bounds"]
        )

        # Preserve the native flow transaction count when identity is
        # partial. Only a fully resolved identity set may replace it with
        # the equivalent resolved count.
        if state == "READY":
            flow["tx_count"] = participant["tx_count"]

    else:
        # Sender-derived participant counts are not wallet evidence.
        # Remove them instead of falling back or guessing.
        market.pop("buyers", None)
        market.pop("sellers", None)
        flow.pop("unique_wallets", None)
        flow.pop("largest_actor_share", None)
        flow.pop("resolved_identity_tx_count", None)

        market["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        market["participant_identity_coverage"] = (
            participant.get("coverage", 0.0)
        )
        market["participant_identity_state"] = "UNKNOWN"
        market["participant_identity_complete"] = False
        market["participant_counts_are_lower_bounds"] = True
        flow["participant_identity_source"] = (
            "TRANSACTION_FROM_ONLY"
        )
        flow["participant_identity_coverage"] = (
            participant.get("coverage", 0.0)
        )
        flow["participant_identity_state"] = "UNKNOWN"
        flow["participant_identity_complete"] = False
        flow["participant_counts_are_lower_bounds"] = True

    return market, flow, participant


def build_market_context(
    row,
    runtime_feed=None,
    news_store=None,
):
    """
    Candidate execution evidence + operational intelligence.

    Scanner evidence is real candidate/source evidence.
    Native flow direction/count is real WSS evidence.
    Participant identity is accepted only from resolved transaction.from.
    Missing evidence stays UNKNOWN/absent; partial identity is explicit and
    conservative rather than being discarded as if no identity existed.
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

    # Preserve the historical no-runtime contract exactly. Tests and callers
    # that explicitly inject a news store can still request news evidence.
    if news_store is not None:
        context = bind_news_market_context(
            context,
            row,
            news_store,
        )

    if runtime_feed is None:
        return context

    # Canonical runtime consumes the shared bounded store. This is a local
    # readmodel lookup only; no Telegram/Discord/X/web IO occurs here.
    if news_store is None:
        context = bind_news_market_context(
            context,
            row,
            DEFAULT_NEWS_EVIDENCE_STORE,
        )

    snapshot = _live_candidate_snapshot(
        runtime_feed,
        row.get("pool"),
        row,
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

    # Engine.run may later ask the same runtime for VUR_KAC shadow/audit
    # evidence. Give that same worker exactly this admission snapshot once.
    _arm_candidate_snapshot(
        runtime_feed,
        row.get("pool"),
        snapshot,
    )

    return context
