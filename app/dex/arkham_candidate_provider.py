from __future__ import annotations

import os
import string
import time
from typing import Any

import requests

from app.dex.arkham_provider import ARKHAM_BASE_URL, HTTP_TIMEOUT

MAX_ADDRESS_TAG_UPDATES = 200
TRADER_SIGNAL_TERMS = (
    "trader",
    "trading",
    "smart money",
    "smart-money",
    "high pnl",
    "high-pnl",
    "profitable",
    "whale",
)


def _headers() -> dict[str, str]:
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    return {"API-Key": key, "Accept": "application/json"} if key else {}


def _evm_address(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if len(text) != 42 or not text.startswith("0x"):
        return None
    if any(ch not in string.hexdigits for ch in text[2:]):
        return None
    return text


def _chain(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {"bnb": "bsc", "bnb chain": "bsc", "binance smart chain": "bsc"}
    return aliases.get(text, text)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "label", "tag", "tagName", "title"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def _rows(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("updates", "items", "data", "results", "addressTags"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return rows
    return []


def _address_from_row(row: dict[str, Any]) -> str | None:
    for value in (
        row.get("address"),
        row.get("walletAddress"),
        row.get("addressValue"),
    ):
        address = _evm_address(value)
        if address:
            return address
    nested = row.get("address")
    if isinstance(nested, dict):
        for key in ("address", "value", "id"):
            address = _evm_address(nested.get(key))
            if address:
                return address
    return None


def _chain_from_row(row: dict[str, Any]) -> str:
    for value in (
        row.get("chain"),
        row.get("chainType"),
        row.get("network"),
    ):
        chain = _chain(value)
        if chain:
            return chain
    nested = row.get("address")
    if isinstance(nested, dict):
        for key in ("chain", "chainType", "network"):
            chain = _chain(nested.get(key))
            if chain:
                return chain
    return ""


def _tag_from_row(row: dict[str, Any]) -> str:
    for key in ("tag", "tagName", "label", "name"):
        text = _text(row.get(key))
        if text:
            return text
    return ""


def _is_trader_signal(tag: str) -> bool:
    lowered = str(tag or "").strip().lower()
    return any(term in lowered for term in TRADER_SIGNAL_TERMS)


def normalize_address_tag_updates(payload: Any, *, limit: int = MAX_ADDRESS_TAG_UPDATES) -> dict[str, Any]:
    limit = max(1, min(int(limit), MAX_ADDRESS_TAG_UPDATES))
    candidates: list[dict[str, Any]] = []
    rejected = 0
    irrelevant = 0
    seen: set[str] = set()

    for row in _rows(payload):
        if len(candidates) >= limit:
            break
        if not isinstance(row, dict):
            rejected += 1
            continue
        address = _address_from_row(row)
        chain = _chain_from_row(row)
        tag = _tag_from_row(row)
        if not address or chain != "bsc":
            rejected += 1
            continue
        if not _is_trader_signal(tag):
            irrelevant += 1
            continue
        wallet_uid = f"bsc:{address}"
        if wallet_uid in seen:
            continue
        seen.add(wallet_uid)
        candidates.append(
            {
                "chain": "bsc",
                "address": address,
                "metadata": {
                    "arkham_tag": tag,
                    "arkham_update_id": row.get("id") or row.get("updateId"),
                },
            }
        )

    return {
        "available": True,
        "provider": "ARKHAM",
        "source": "ARKHAM_ADDRESS_TAG_UPDATE",
        "candidates": candidates,
        "candidate_count": len(candidates),
        "rejected": rejected,
        "irrelevant": irrelevant,
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


def fetch_address_tag_candidate_updates(*, limit: int = MAX_ADDRESS_TAG_UPDATES) -> dict[str, Any]:
    headers = _headers()
    if not headers:
        return {
            "available": False,
            "reason": "ARKHAM_NOT_CONFIGURED",
            "source": "ARKHAM_ADDRESS_TAG_UPDATE",
            "candidates": [],
            "success_authority": False,
            "trade_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
    try:
        response = requests.get(
            f"{ARKHAM_BASE_URL}/intelligence/address_tags/updates",
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException:
        return {
            "available": False,
            "reason": "ARKHAM_UNAVAILABLE",
            "source": "ARKHAM_ADDRESS_TAG_UPDATE",
            "candidates": [],
        }
    if response.status_code != 200:
        return {
            "available": False,
            "reason": f"ARKHAM_HTTP_{response.status_code}",
            "source": "ARKHAM_ADDRESS_TAG_UPDATE",
            "candidates": [],
        }
    try:
        payload = response.json()
    except ValueError:
        return {
            "available": False,
            "reason": "ARKHAM_INVALID_JSON",
            "source": "ARKHAM_ADDRESS_TAG_UPDATE",
            "candidates": [],
        }
    out = normalize_address_tag_updates(payload, limit=limit)
    out["fetched_at"] = time.time()
    return out
