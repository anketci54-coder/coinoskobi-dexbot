from __future__ import annotations

import os
import time
from typing import Any, Callable

import requests

from app.dex.wallet_candidate_discovery import ingest_wallet_candidates

ARKHAM_BASE_URL = "https://api.arkm.com"
HTTP_TIMEOUT_SECONDS = 8.0
MAX_UPDATE_ROWS = 500
OFFICIAL_ENDPOINTS = {
    "ADDRESS_TAG_UPDATES": "/intelligence/address_tags/updates",
    "ADDRESS_UPDATES": "/intelligence/addresses/updates",
}


def _headers() -> dict[str, str]:
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    return {"API-Key": key, "Accept": "application/json"} if key else {}


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = None
        for key in ("updates", "results", "data", "items", "addresses", "addressTags"):
            value = payload.get(key)
            if isinstance(value, list):
                raw = value
                break
        if raw is None:
            raw = []
    else:
        raw = []
    return [dict(row) for row in raw[:MAX_UPDATE_ROWS] if isinstance(row, dict)]


def _address_from_row(row: dict[str, Any]) -> str:
    for key in ("address", "addressValue", "address_value"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    address = row.get("addressInfo") or row.get("address_info")
    if isinstance(address, dict):
        value = address.get("address") or address.get("value")
        if isinstance(value, str):
            return value.strip()
    return ""


def _chain_from_row(row: dict[str, Any]) -> str:
    value = row.get("chain") or row.get("chainType") or row.get("chain_type") or ""
    if isinstance(value, dict):
        value = value.get("id") or value.get("name") or value.get("chain") or ""
    text = str(value or "").strip().lower()
    aliases = {"bnb": "bsc", "bnb chain": "bsc", "binance-smart-chain": "bsc"}
    return aliases.get(text, text)


def normalize_arkham_update_candidates(payload: Any) -> list[dict[str, Any]]:
    """Normalize official Arkham intelligence update rows into BSC candidate rows.

    This function only discovers candidates. It never assigns SUCCESSFUL status.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _rows(payload):
        address = _address_from_row(row)
        chain = _chain_from_row(row)
        if chain != "bsc" or not address:
            continue
        wallet_key = address.strip().lower()
        if wallet_key in seen:
            continue
        seen.add(wallet_key)
        metadata = {
            key: row.get(key)
            for key in ("tag", "tagName", "label", "entity", "entityType", "timestamp", "updatedAt")
            if row.get(key) is not None
        }
        out.append({"chain": "bsc", "address": address, "metadata": metadata or None})
    return out


def fetch_official_updates(
    kind: str,
    *,
    params: dict[str, Any] | None = None,
    getter: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    kind = str(kind or "").strip().upper()
    endpoint = OFFICIAL_ENDPOINTS.get(kind)
    if endpoint is None:
        raise ValueError("UNSUPPORTED_ARKHAM_UPDATE_FEED")
    headers = _headers()
    if not headers:
        return {"available": False, "reason": "ARKHAM_NOT_CONFIGURED", "updates": []}
    try:
        response = getter(
            ARKHAM_BASE_URL + endpoint,
            params=dict(params or {}),
            headers=headers,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return {"available": False, "reason": "ARKHAM_UNAVAILABLE", "updates": []}
    if getattr(response, "status_code", None) != 200:
        return {
            "available": False,
            "reason": f"ARKHAM_HTTP_{getattr(response, 'status_code', 'UNKNOWN')}",
            "updates": [],
        }
    try:
        payload = response.json()
    except ValueError:
        return {"available": False, "reason": "ARKHAM_INVALID_JSON", "updates": []}
    return {
        "available": True,
        "kind": kind,
        "updates": _rows(payload),
        "fetched_at": time.time(),
        "read_only": True,
        "success_authority": False,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }


def ingest_official_updates(
    db_path,
    result: dict[str, Any],
    *,
    source_key: str,
    observed_at: float | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("available") is not True:
        return {
            "state": "PROVIDER_UNAVAILABLE",
            "accepted": 0,
            "success_authority": False,
            "trade_authority": False,
            "execution_authority": False,
        }
    kind = str(result.get("kind") or "").upper()
    source = {
        "ADDRESS_TAG_UPDATES": "ARKHAM_ADDRESS_TAG_UPDATE",
        "ADDRESS_UPDATES": "ARKHAM_TRADER_TAG",
    }.get(kind)
    if source is None:
        raise ValueError("UNSUPPORTED_ARKHAM_UPDATE_FEED")
    candidates = normalize_arkham_update_candidates(result.get("updates") or [])
    return ingest_wallet_candidates(
        db_path,
        candidates,
        source=source,
        source_key=source_key,
        provider="ARKHAM",
        observed_at=observed_at,
    )
