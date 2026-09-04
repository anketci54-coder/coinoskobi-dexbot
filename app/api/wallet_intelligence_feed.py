from __future__ import annotations

import math
import os
import time
from typing import Any

import requests


ARKHAM_BASE_URL = "https://api.arkm.com"
MAX_TRACKED_WALLETS = 500
MAX_TRACKED_ASSETS_PER_WALLET = 128
HTTP_TIMEOUT = 8.0


def _headers() -> dict[str, str]:
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    return {"API-Key": key, "Accept": "application/json"} if key else {}


def _finite(value: Any, *, allow_none: bool = True) -> float | None:
    if value is None and allow_none:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def arkham_config_status() -> dict[str, Any]:
    configured = bool(os.getenv("ARKHAM_API_KEY", "").strip())
    return {
        "provider": "ARKHAM",
        "configured": configured,
        "max_tracked_wallets": MAX_TRACKED_WALLETS,
        "max_tracked_assets_per_wallet": MAX_TRACKED_ASSETS_PER_WALLET,
        "discovery_mode": "BOUNDED_SEED_LIST",
        "holdings_mode": "SUCCESSFUL_WALLETS_ONLY",
        "note": (
            "Arkham API is used for read-only address/entity intelligence, swaps, "
            "and bounded holdings enrichment. Successful-wallet qualification "
            "remains internal realized-outcome evidence."
        ),
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
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
    """Bounded read-only Arkham enrichment for a known address."""
    address = str(address or "").strip()
    if not address:
        raise ValueError("ADDRESS_REQUIRED")
    headers = _headers()
    if not headers:
        return {"available": False, "reason": "ARKHAM_NOT_CONFIGURED", "swaps": []}

    limit = max(1, min(int(limit), 100))
    try:
        response = requests.get(
            f"{ARKHAM_BASE_URL}/swaps",
            params={"address": address, "chains": chain, "limit": limit},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException:
        return {"available": False, "reason": "ARKHAM_UNAVAILABLE", "swaps": []}

    if response.status_code != 200:
        return {
            "available": False,
            "reason": f"ARKHAM_HTTP_{response.status_code}",
            "swaps": [],
        }
    try:
        payload = response.json()
    except ValueError:
        return {"available": False, "reason": "ARKHAM_INVALID_JSON", "swaps": []}

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


def normalize_address_balances(
    payload: Any,
    *,
    chain: str = "bsc",
    limit: int = MAX_TRACKED_ASSETS_PER_WALLET,
) -> list[dict[str, Any]]:
    """Normalize one chain from Arkham's chain-keyed address balance payload."""
    chain = str(chain or "bsc").strip().lower() or "bsc"
    limit = max(1, min(int(limit), MAX_TRACKED_ASSETS_PER_WALLET))
    if not isinstance(payload, dict):
        return []

    balances = payload.get("balances")
    if not isinstance(balances, dict):
        return []
    rows = balances.get(chain)
    if not isinstance(rows, list):
        return []

    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        balance = _finite(row.get("balance"), allow_none=False)
        if balance is None or balance < 0:
            continue

        token_address = str(
            row.get("ethereumAddress")
            or row.get("tokenAddress")
            or ""
        ).strip().lower()
        pricing_id = str(row.get("id") or "").strip().lower()
        symbol = str(row.get("symbol") or "").strip()
        name = str(row.get("name") or "").strip()
        fallback_id = pricing_id or symbol.lower() or name.lower()
        if token_address:
            token_id = f"{chain}:{token_address}"
        elif fallback_id:
            token_id = f"{chain}:arkham:{fallback_id}"
        else:
            continue

        value_usd = _finite(row.get("usd"))
        price_usd = _finite(row.get("price"))
        normalized.append({
            "token_id": token_id,
            "token_address": token_address or None,
            "pricing_id": pricing_id or None,
            "symbol": symbol or None,
            "name": name or None,
            "balance": balance,
            "value_usd": value_usd,
            "price_usd": price_usd,
            "price_change_24h_pct": _finite(row.get("priceChange24hPercent")),
            "quote_time": row.get("quoteTime"),
            "source": "ARKHAM",
        })

    normalized.sort(
        key=lambda row: (
            row["value_usd"] is not None,
            row["value_usd"] or 0.0,
            row["balance"],
        ),
        reverse=True,
    )
    return normalized[:limit]


def fetch_balances_for_address(
    address: str,
    *,
    chain: str = "bsc",
    limit: int = MAX_TRACKED_ASSETS_PER_WALLET,
) -> dict[str, Any]:
    """Fetch a complete bounded holdings snapshot for one known address."""
    address = str(address or "").strip()
    chain = str(chain or "bsc").strip().lower() or "bsc"
    if not address:
        raise ValueError("ADDRESS_REQUIRED")
    headers = _headers()
    if not headers:
        return {
            "available": False,
            "reason": "ARKHAM_NOT_CONFIGURED",
            "holdings": [],
        }

    try:
        response = requests.get(
            f"{ARKHAM_BASE_URL}/balances/address/{address}",
            params={"chains": chain},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException:
        return {
            "available": False,
            "reason": "ARKHAM_UNAVAILABLE",
            "holdings": [],
        }

    if response.status_code != 200:
        return {
            "available": False,
            "reason": f"ARKHAM_HTTP_{response.status_code}",
            "holdings": [],
        }
    try:
        payload = response.json()
    except ValueError:
        return {
            "available": False,
            "reason": "ARKHAM_INVALID_JSON",
            "holdings": [],
        }

    balances = payload.get("balances") if isinstance(payload, dict) else None
    if not isinstance(balances, dict):
        return {
            "available": False,
            "reason": "ARKHAM_INVALID_BALANCES",
            "holdings": [],
        }

    totals = payload.get("totalBalance") if isinstance(payload, dict) else {}
    total_usd = totals.get(chain) if isinstance(totals, dict) else None
    return {
        "available": True,
        "address": address,
        "chain": chain,
        "holdings": normalize_address_balances(payload, chain=chain, limit=limit),
        "total_value_usd": _finite(total_usd),
        "complete_snapshot": True,
        "fetched_at": time.time(),
        "read_only": True,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
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
