from __future__ import annotations

import os
import time
from typing import Any, Mapping

import requests

from app.dex.arkham_provider import ARKHAM_BASE_URL, HTTP_TIMEOUT


MAX_UPDATE_ROWS = 250
UPDATE_ENDPOINTS = {
    "ADDRESS_TAGS": "/intelligence/address_tags/updates",
    "ADDRESSES": "/intelligence/addresses/updates",
}


def _headers() -> dict[str, str]:
    key = os.getenv("ARKHAM_API_KEY", "").strip()
    return {"API-Key": key, "Accept": "application/json"} if key else {}


def _result(state: str, **payload: Any) -> dict[str, Any]:
    return {
        "available": state == "READY",
        "state": state,
        "provider": "ARKHAM",
        "read_only": True,
        "success_authority": False,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
        **payload,
    }


def fetch_intelligence_updates(
    kind: str,
    *,
    params: Mapping[str, Any] | None = None,
    session=requests,
) -> dict[str, Any]:
    """Fetch a documented Arkham intelligence update feed without inventing query params."""
    kind = str(kind or "").strip().upper()
    endpoint = UPDATE_ENDPOINTS.get(kind)
    if endpoint is None:
        raise ValueError("UNSUPPORTED_ARKHAM_UPDATE_KIND")

    headers = _headers()
    if not headers:
        return _result("ARKHAM_NOT_CONFIGURED", kind=kind, rows=[])

    request_params = dict(params or {})
    try:
        response = session.get(
            f"{ARKHAM_BASE_URL}{endpoint}",
            params=request_params or None,
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException:
        return _result("ARKHAM_UNAVAILABLE", kind=kind, rows=[])

    if response.status_code != 200:
        return _result(f"ARKHAM_HTTP_{response.status_code}", kind=kind, rows=[])
    try:
        payload = response.json()
    except ValueError:
        return _result("ARKHAM_INVALID_JSON", kind=kind, rows=[])

    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        candidate = payload.get("updates")
        if not isinstance(candidate, list):
            candidate = payload.get("data")
        if not isinstance(candidate, list):
            candidate = payload.get("results")
        rows = candidate if isinstance(candidate, list) else []
    else:
        rows = []

    capped = len(rows) > MAX_UPDATE_ROWS
    return _result(
        "READY",
        kind=kind,
        endpoint=endpoint,
        rows=rows[:MAX_UPDATE_ROWS],
        row_count=min(len(rows), MAX_UPDATE_ROWS),
        capped=capped,
        fetched_at=time.time(),
    )
