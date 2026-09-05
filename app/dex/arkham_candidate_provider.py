from __future__ import annotations

import os
import string
import time
from typing import Any, Iterable

import requests

from app.dex.arkham_provider import ARKHAM_BASE_URL, HTTP_TIMEOUT


MAX_UPDATE_ROWS = 500
MAX_CANDIDATES_PER_FETCH = 200

# Conservative discovery-only signals. They never grant SUCCESSFUL status.
CANDIDATE_TAG_TERMS = (
    "trader",
    "smart money",
    "smart-money",
    "smart_money",
    "whale",
)

_BSC_ALIASES = {
    "bsc",
    "bnb",
    "bnb chain",
    "bnb-chain",
    "binance smart chain",
    "binance-smart-chain",
}


def _headers() -> dict[str, str]:
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    return {"API-Key": key, "Accept": "application/json"} if key else {}


def _is_evm_address(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return (
        len(text) == 42
        and text.startswith("0x")
        and all(ch in string.hexdigits for ch in text[2:])
    )


def _chain(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return "bsc" if text in _BSC_ALIASES else None


def _text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        text = value.strip()
        if text:
            yield text
        return
    if isinstance(value, dict):
        for key in ("name", "label", "tag", "type", "displayName", "display_name"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                yield item.strip()
        return
    if isinstance(value, list):
        for item in value:
            yield from _text_values(item)


def _tag_text(row: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("tag", "tags", "tagName", "tag_name", "label", "labels"):
        values.extend(_text_values(row.get(key)))
    return " ".join(values).strip().lower()


def _candidate_signal(tag_text: str) -> str | None:
    normalized = " ".join(str(tag_text or "").lower().split())
    for term in CANDIDATE_TAG_TERMS:
        if term in normalized:
            return term.upper().replace("-", "_").replace(" ", "_")
    return None


def _nested_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _extract_identity(row: dict[str, Any]) -> tuple[str, str] | None:
    address_value = _nested_value(row, "address", "walletAddress", "wallet_address")
    chain_value = _nested_value(row, "chain", "chainType", "chain_type", "network")

    if isinstance(address_value, dict):
        address_obj = address_value
        chain_value = chain_value or _nested_value(
            address_obj,
            "chain",
            "chainType",
            "chain_type",
            "network",
        )
        address_value = _nested_value(
            address_obj,
            "address",
            "value",
            "walletAddress",
            "wallet_address",
        )

    chain = _chain(chain_value)
    address = str(address_value or "").strip().lower()
    if chain != "bsc" or not _is_evm_address(address):
        return None
    return chain, address


def _rows(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload[:MAX_UPDATE_ROWS]
    if not isinstance(payload, dict):
        return []
    for key in ("updates", "addressTags", "address_tags", "results", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value[:MAX_UPDATE_ROWS]
        if isinstance(value, dict):
            for nested_key in ("updates", "results", "items", "data"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return nested[:MAX_UPDATE_ROWS]
    return []


def normalize_address_tag_candidates(
    payload: Any,
    *,
    limit: int = MAX_CANDIDATES_PER_FETCH,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), MAX_CANDIDATES_PER_FETCH))
    candidates: list[dict[str, Any]] = []
    rejected = ignored = 0
    seen: set[str] = set()

    for raw in _rows(payload):
        if not isinstance(raw, dict):
            rejected += 1
            continue
        identity = _extract_identity(raw)
        if identity is None:
            rejected += 1
            continue
        tag_text = _tag_text(raw)
        signal = _candidate_signal(tag_text)
        if signal is None:
            ignored += 1
            continue
        chain, address = identity
        wallet_uid = f"{chain}:{address}"
        if wallet_uid in seen:
            continue
        seen.add(wallet_uid)
        candidates.append(
            {
                "chain": chain,
                "address": address,
                "metadata": {
                    "arkham_signal": signal,
                    "arkham_tag_text": tag_text[:512],
                },
            }
        )
        if len(candidates) >= limit:
            break

    return {
        "available": True,
        "provider": "ARKHAM",
        "source": "ARKHAM_ADDRESS_TAG_UPDATE",
        "candidates": candidates,
        "candidate_count": len(candidates),
        "rejected_rows": rejected,
        "ignored_rows": ignored,
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


def fetch_address_tag_updates(
    *,
    params: dict[str, Any] | None = None,
    limit: int = MAX_CANDIDATES_PER_FETCH,
) -> dict[str, Any]:
    """Fetch Arkham address-tag updates without inventing undocumented query params.

    `params` is passed through only when the caller has a documented/verified
    update cursor/window. This adapter itself never guesses pagination fields.
    """
    headers = _headers()
    if not headers:
        return {
            "available": False,
            "reason": "ARKHAM_NOT_CONFIGURED",
            "candidates": [],
        }

    try:
        response = requests.get(
            f"{ARKHAM_BASE_URL}/intelligence/address_tags/updates",
            params=dict(params or {}),
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException:
        return {
            "available": False,
            "reason": "ARKHAM_UNAVAILABLE",
            "candidates": [],
        }

    if response.status_code != 200:
        return {
            "available": False,
            "reason": f"ARKHAM_HTTP_{response.status_code}",
            "candidates": [],
        }
    try:
        payload = response.json()
    except ValueError:
        return {
            "available": False,
            "reason": "ARKHAM_INVALID_JSON",
            "candidates": [],
        }

    result = normalize_address_tag_candidates(payload, limit=limit)
    result["fetched_at"] = time.time()
    return result
