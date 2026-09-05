from __future__ import annotations

from typing import Any

from app.dex.arkham_provider import (
    ARKHAM_BASE_URL,
    HTTP_TIMEOUT,
    MAX_TRACKED_ASSETS_PER_WALLET,
    MAX_TRACKED_WALLETS,
    arkham_config_status,
    fetch_balances_for_address,
    fetch_swaps_for_address,
    normalize_address_balances,
)


__all__ = [
    "ARKHAM_BASE_URL",
    "HTTP_TIMEOUT",
    "MAX_TRACKED_ASSETS_PER_WALLET",
    "MAX_TRACKED_WALLETS",
    "arkham_config_status",
    "fetch_balances_for_address",
    "fetch_swaps_for_address",
    "normalize_address_balances",
    "score_wallet_candidate",
    "select_top_wallets",
]


def score_wallet_candidate(row: dict[str, Any]) -> float:
    """Score a normalized wallet candidate without treating PnL alone as skill."""
    trades = max(0, int(row.get("trade_count") or 0))
    win_rate = max(0.0, min(1.0, float(row.get("win_rate") or 0.0)))
    roi = max(-1.0, min(10.0, float(row.get("roi") or 0.0)))
    recency = max(0.0, min(1.0, float(row.get("recency_score") or 0.0)))
    consistency = max(0.0, min(1.0, float(row.get("consistency") or 0.0)))
    sample = min(1.0, trades / 50.0)
    roi_score = max(0.0, min(1.0, roi / 2.0))
    return round(
        100.0 * (
            0.30 * win_rate
            + 0.25 * consistency
            + 0.20 * sample
            + 0.15 * recency
            + 0.10 * roi_score
        ),
        2,
    )


def select_top_wallets(
    rows: list[dict[str, Any]],
    *,
    limit: int = MAX_TRACKED_WALLETS,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), MAX_TRACKED_WALLETS))
    eligible = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("address"):
            continue
        if row.get("is_exchange") or row.get("is_contract"):
            continue
        item = dict(row)
        item["score"] = score_wallet_candidate(item)
        eligible.append(item)
    eligible.sort(
        key=lambda item: (item["score"], int(item.get("trade_count") or 0)),
        reverse=True,
    )
    return eligible[:limit]
