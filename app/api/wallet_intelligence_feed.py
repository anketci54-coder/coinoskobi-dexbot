from __future__ import annotations

import os
import time
from typing import Any

import requests


ARKHAM_BASE_URL = "https://api.arkm.com"
MAX_TRACKED_WALLETS = 500
HTTP_TIMEOUT = 8.0


def _headers() -> dict[str, str]:
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    return {"API-Key": key, "Accept": "application/json"} if key else {}


def arkham_config_status() -> dict[str, Any]:
    configured = bool(os.getenv("ARKHAM_API_KEY", "").strip())
    return {
        "provider": "ARKHAM",
        "configured": configured,
        "max_tracked_wallets": MAX_TRACKED_WALLETS,
        "discovery_mode": "BOUNDED_SEED_LIST",
        "note": (
            "Arkham API is used for address/entity intelligence and swaps. "
            "Top-wallet discovery requires a supported ranking source or curated seed list."
        ),
        "trade_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }


def fetch_swaps_for_address(
    address: str,
    *,
    chain: str = "bsc",
    limit: int = 100,
) -> dict[str, Any]:
    """Bounded read-only Arkham enrichment for a known address.

    This adapter deliberately does not scrape the Arkham web UI and does not
    invent a top-500 leaderboard endpoint. Addresses enter through a verified
    seed/ranking source and are then enriched here.
    """
    address = str(address or "").strip()
    if not address:
        raise ValueError("ADDRESS_REQUIRED")
    headers = _headers()
    if not headers:
        return {"available": False, "reason": "ARKHAM_NOT_CONFIGURED", "swaps": []}

    limit = max(1, min(int(limit), 100))
    response = requests.get(
        f"{ARKHAM_BASE_URL}/swaps",
        params={"address": address, "chains": chain, "limit": limit},
        headers=headers,
        timeout=HTTP_TIMEOUT,
    )
    if response.status_code != 200:
        return {
            "available": False,
            "reason": f"ARKHAM_HTTP_{response.status_code}",
            "swaps": [],
        }
    payload = response.json()
    rows = payload.get("swaps") if isinstance(payload, dict) else payload
    return {
        "available": True,
        "address": address,
        "chain": chain,
        "swaps": rows if isinstance(rows, list) else [],
        "fetched_at": time.time(),
        "read_only": True,
        "trade_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


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


def select_top_wallets(rows: list[dict[str, Any]], *, limit: int = MAX_TRACKED_WALLETS) -> list[dict[str, Any]]:
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
    eligible.sort(key=lambda item: (item["score"], int(item.get("trade_count") or 0)), reverse=True)
    return eligible[:limit]
