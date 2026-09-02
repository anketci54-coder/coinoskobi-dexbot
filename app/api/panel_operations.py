from __future__ import annotations

from typing import Any


PROVIDER_MESSAGES = {
    "HEALTHY": "Veri akisi normal",
    "RATE_LIMIT": "Veri saglayici kapasitesi dolu",
    "QUOTA": "Veri saglayici kapasitesi dolu",
    "FORBIDDEN": "Veri saglayici erisimi sinirli",
    "TIMEOUT": "Veri saglayici gec cevap veriyor",
    "DOWN": "Veri saglayici kullanilamiyor",
    "UNKNOWN": "Veri saglayici durumu belirsiz",
}

WATCH_EXIT_MESSAGES = {
    "VERIFIED": "Cikis dogrulandi",
    "LIMITED": "Cikis kismen dogrulandi",
    "UNVERIFIED": "Henuz dogrulanmadi",
    "DEFERRED": "Cikis dogrulamasi sirada",
}

DECISION_MESSAGES = {
    "PLAN_BLOCKED": "Islem sartlari olusmadi",
    "POSITION_SIZING_BLOCKED": "Uygun pozisyon boyutu olusmadi",
    "PAPER_TRADE_OPENED": "Paper islem acildi",
    "WATCH": "Izlemeye alindi",
    "REJECT": "Aday elendi",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def provider_message(state: Any) -> str:
    key = _text(state).upper() or "UNKNOWN"
    return PROVIDER_MESSAGES.get(key, PROVIDER_MESSAGES["UNKNOWN"])


def watch_exit_message(state: Any) -> str:
    key = _text(state).upper() or "UNVERIFIED"
    return WATCH_EXIT_MESSAGES.get(key, WATCH_EXIT_MESSAGES["UNVERIFIED"])


def decision_message(reason: Any) -> str:
    key = _text(reason).upper()
    return DECISION_MESSAGES.get(key, "Karar kaydi mevcut")


def system_mode(*, runtime_active: bool, data_healthy: bool, incident: bool = False) -> str:
    if incident:
        return "INCIDENT"
    if not runtime_active:
        return "SAFE"
    if not data_healthy:
        return "DEGRADED"
    return "HEALTHY"


def build_operations_summary(
    *,
    runtime_active: bool,
    provider_state: str,
    watch: dict[str, Any] | None = None,
    paper: dict[str, Any] | None = None,
    radar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    watch = dict(watch or {})
    paper = dict(paper or {})
    radar = dict(radar or {})

    provider_key = _text(provider_state).upper() or "UNKNOWN"
    data_healthy = provider_key == "HEALTHY"
    mode = system_mode(
        runtime_active=runtime_active,
        data_healthy=data_healthy,
    )

    open_watch = int(watch.get("open") or 0)
    verified_watch = int(watch.get("verified") or 0)
    limited_watch = int(watch.get("limited") or 0)

    return {
        "system": {
            "mode": mode,
            "label": {
                "HEALTHY": "Sistem normal",
                "DEGRADED": "Sistem kisitli veriyle calisiyor",
                "SAFE": "Sistem guvenli beklemede",
                "INCIDENT": "Sistem olayi inceliyor",
            }[mode],
        },
        "data": {
            "label": provider_message(provider_key),
            "healthy": data_healthy,
        },
        "watch": {
            "open": open_watch,
            "verified": verified_watch,
            "limited": limited_watch,
            "label": (
                f"{verified_watch} cikis dogrulandi"
                if verified_watch
                else (
                    "Cikis dogrulamalari suruyor"
                    if open_watch
                    else "Izlemede kayit yok"
                )
            ),
        },
        "paper": {
            "open": int(paper.get("open") or 0),
            "closed": int(paper.get("closed") or 0),
            "net_pnl_usdt": paper.get("net_pnl_usdt"),
        },
        "radar": {
            "cold": int(radar.get("cold") or 0),
            "warm": int(radar.get("warm") or 0),
            "hot": int(radar.get("hot") or 0),
        },
        "technical_details_hidden": True,
    }


def build_vezir_context(
    *,
    operations: dict[str, Any],
    watch: dict[str, Any] | None = None,
    paper: dict[str, Any] | None = None,
    radar: dict[str, Any] | None = None,
    wallet: dict[str, Any] | None = None,
    whale: dict[str, Any] | None = None,
    news: dict[str, Any] | None = None,
    freshness_seconds: float | None = None,
) -> dict[str, Any]:
    """Bounded read-only context for Vezir.

    This contract intentionally excludes raw RPC URLs, secrets, environment
    values, process controls, SQL handles and execution-capable objects.
    """

    return {
        "role": "OPERASYON_ANALISTI",
        "authority": "READ_ONLY",
        "operations": dict(operations or {}),
        "watch": dict(watch or {}),
        "paper": dict(paper or {}),
        "radar": dict(radar or {}),
        "wallet": dict(wallet or {}),
        "whale": dict(whale or {}),
        "news": dict(news or {}),
        "freshness_seconds": freshness_seconds,
        "permissions": {
            "trade": False,
            "wallet": False,
            "signing": False,
            "database_write": False,
            "runtime_control": False,
            "deployment": False,
        },
        "response_policy": {
            "technical_by_default": False,
            "fabricate_missing_data": False,
            "prefer_summary_reason_action": True,
        },
    }
