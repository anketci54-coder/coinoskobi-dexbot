from __future__ import annotations

import os
import string
import time
from datetime import datetime, timezone
from typing import Any

import requests

from app.dex.arkham_provider import ARKHAM_BASE_URL, HTTP_TIMEOUT


MAX_DISCOVERY_ROWS_PER_FEED = 250
_ENDPOINTS = {
    "ADDRESS_TAG_UPDATES": "/intelligence/address_tags/updates",
    "ADDRESS_UPDATES": "/intelligence/addresses/updates",
}
_CANDIDATE_TAG_TERMS = (
    "trader",
    "smart money",
    "smart-money",
    "smart_money",
    "high pnl",
    "high-pnl",
    "high_pnl",
    "profitable",
)
_BSC_ALIASES = {"bsc", "bnb", "bnbchain", "bnb chain", "bnb-chain", "binance-smart-chain", "binance smart chain"}


def _headers() -> dict[str, str]:
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    return {"API-Key": key, "Accept": "application/json"} if key else {}


def _iso_utc(value: Any) -> str:
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    text = str(value or "").strip()
    if not text:
        raise ValueError("SINCE_REQUIRED")
    return text


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("updates", "items", "data", "addresses", "addressTags", "address_tags"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            for nested_key in ("updates", "items", "data"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return [row for row in nested if isinstance(row, dict)]
    return []


def _has_update_shape(payload: Any) -> bool:
    """Distinguish a valid empty update page from an unknown provider shape."""
    if isinstance(payload, list):
        return True
    if not isinstance(payload, dict):
        return False
    for key in ("updates", "items", "data", "addresses", "addressTags", "address_tags"):
        value = payload.get(key)
        if isinstance(value, list):
            return True
        if isinstance(value, dict):
            for nested_key in ("updates", "items", "data"):
                if isinstance(value.get(nested_key), list):
                    return True
    return False


def _address_chain(row: dict[str, Any]) -> tuple[str | None, str | None]:
    candidates = [row]
    for key in ("address", "addressInfo", "address_info", "subject", "target"):
        value = row.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    for item in candidates:
        address = item.get("address")
        if isinstance(address, dict):
            nested = address
            address = nested.get("address") or nested.get("value")
            item = {**item, **nested}
        address_text = str(
            address
            or item.get("addressAddress")
            or item.get("wallet")
            or item.get("walletAddress")
            or ""
        ).strip().lower()
        chain_text = str(
            item.get("chain")
            or item.get("chainType")
            or item.get("network")
            or row.get("chain")
            or row.get("chainType")
            or ""
        ).strip().lower()
        if address_text:
            return address_text, chain_text or None
    return None, None


def _is_evm_address(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return (
        len(text) == 42
        and text.startswith("0x")
        and all(ch in string.hexdigits for ch in text[2:])
    )


def _text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        out: list[str] = []
        for key in ("name", "label", "tag", "type", "displayName", "display_name"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_text_values(item))
        return out
    return []


def _tag_text(row: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("tag", "tags", "tagName", "tag_name", "label", "labels"):
        values.extend(_text_values(row.get(key)))
    return " ".join(values).strip().lower()


def _candidate_signal(tag_text: str) -> str | None:
    normalized = " ".join(str(tag_text or "").lower().split())
    for term in _CANDIDATE_TAG_TERMS:
        if term in normalized:
            return term.upper().replace("-", "_").replace(" ", "_")
    return None


def normalize_discovery_updates(
    payload: Any,
    *,
    feed: str,
    limit: int = MAX_DISCOVERY_ROWS_PER_FEED,
) -> list[dict[str, Any]]:
    feed = str(feed or "").strip().upper()
    if feed not in _ENDPOINTS:
        raise ValueError("UNSUPPORTED_ARKHAM_DISCOVERY_FEED")
    limit = max(1, min(int(limit), MAX_DISCOVERY_ROWS_PER_FEED))

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in _rows(payload):
        address, chain = _address_chain(row)
        if not address or not _is_evm_address(address):
            continue
        chain = (chain or "").lower()
        if chain not in _BSC_ALIASES:
            continue

        tag_text = _tag_text(row)
        signal = _candidate_signal(tag_text)
        if feed == "ADDRESS_TAG_UPDATES" and signal is None:
            continue

        key = ("bsc", address)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "chain": "bsc",
                "address": address,
                "metadata": {
                    "arkham_feed": feed,
                    "arkham_signal": signal,
                    "tag": row.get("tag") or row.get("tagName") or row.get("label"),
                    "entity": row.get("entity") or row.get("entityName"),
                    "updated_at": row.get("updatedAt") or row.get("updated_at") or row.get("timestamp"),
                },
            }
        )
        if len(out) >= limit:
            break
    return out


def fetch_discovery_updates(
    *,
    feed: str,
    since: Any,
    limit: int = MAX_DISCOVERY_ROWS_PER_FEED,
) -> dict[str, Any]:
    feed = str(feed or "").strip().upper()
    endpoint = _ENDPOINTS.get(feed)
    if endpoint is None:
        raise ValueError("UNSUPPORTED_ARKHAM_DISCOVERY_FEED")

    headers = _headers()
    if not headers:
        return {
            "available": False,
            "reason": "ARKHAM_NOT_CONFIGURED",
            "feed": feed,
            "candidates": [],
        }

    since_text = _iso_utc(since)
    try:
        response = requests.get(
            f"{ARKHAM_BASE_URL}{endpoint}",
            params={"since": since_text},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException:
        return {
            "available": False,
            "reason": "ARKHAM_UNAVAILABLE",
            "feed": feed,
            "candidates": [],
        }

    if response.status_code != 200:
        return {
            "available": False,
            "reason": f"ARKHAM_HTTP_{response.status_code}",
            "feed": feed,
            "candidates": [],
        }
    try:
        payload = response.json()
    except ValueError:
        return {
            "available": False,
            "reason": "ARKHAM_INVALID_JSON",
            "feed": feed,
            "candidates": [],
        }
    if not _has_update_shape(payload):
        return {
            "available": False,
            "reason": "ARKHAM_INVALID_UPDATES_PAYLOAD",
            "feed": feed,
            "candidates": [],
        }

    candidates = normalize_discovery_updates(payload, feed=feed, limit=limit)
    return {
        "available": True,
        "feed": feed,
        "since": since_text,
        "candidates": candidates,
        "returned_candidates": len(candidates),
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
