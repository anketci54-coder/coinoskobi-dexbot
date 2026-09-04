from __future__ import annotations

import threading
import time
from typing import Any

from app.chains.bsc import w3


_CACHE_LOCK = threading.RLock()
_CACHE: dict[str, Any] = {
    "checked_at": 0.0,
    "payload": None,
}
TTL_SECONDS = 30.0


def _status() -> dict[str, Any]:
    fn = getattr(w3.provider, "status", None)
    return fn() if callable(fn) else {}


def provider_health_snapshot(*, force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get("payload")
        checked_at = float(_CACHE.get("checked_at") or 0.0)
        if not force and cached is not None and now - checked_at < TTL_SECONDS:
            return dict(cached)

    chain_ok = False
    error_type = None
    try:
        chain_ok = int(w3.eth.chain_id) == 56
    except Exception as exc:
        error_type = type(exc).__name__

    status = _status()
    private = dict(status.get("private") or status)
    private_rows = list(private.get("providers") or [])
    private_configured = int(private.get("provider_count") or len(private_rows) or 0)
    private_open = sum(1 for row in private_rows if row.get("circuit_open"))
    private_healthy = max(0, private_configured - private_open)

    fallback_enabled = bool(status.get("public_fallback_enabled"))
    fallback_count = int(status.get("public_provider_count") or 0)
    last_source = str(status.get("last_source") or "PRIVATE")
    fallback_active = chain_ok and last_source == "OFFICIAL_BNB_PUBLIC"

    if chain_ok and not fallback_active:
        state = "HEALTHY"
        label = f"RPC sağlıklı · {private_healthy}/{private_configured} özel provider kullanılabilir"
    elif chain_ok and fallback_active:
        state = "DEGRADED"
        label = "Özel RPC provider'ları sorunlu; resmi BNB read-only fallback devrede"
    else:
        state = "UNAVAILABLE"
        label = "RPC erişimi kullanılamıyor"

    payload = {
        "state": state,
        "label": label,
        "chain_id_ok": chain_ok,
        "private_provider_count": private_configured,
        "private_healthy_count": private_healthy,
        "private_circuit_open_count": private_open,
        "public_fallback_enabled": fallback_enabled,
        "public_provider_count": fallback_count,
        "public_fallback_active": fallback_active,
        "last_source": last_source,
        "error_type": error_type,
        "eth_getLogs_public_fallback": False,
        "transaction_submission_public_fallback": False,
        "secret_values_exposed": False,
        "trade_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }

    with _CACHE_LOCK:
        _CACHE["checked_at"] = now
        _CACHE["payload"] = dict(payload)

    return payload


def register_provider_health_route(app) -> None:
    @app.get("/api/provider-health-v2")
    def provider_health_v2() -> dict[str, Any]:
        return provider_health_snapshot()
