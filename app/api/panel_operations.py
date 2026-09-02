from __future__ import annotations

from typing import Any


_REASON_LABELS = {
    "PLAN_BLOCKED": "İşlem şartları oluşmadı",
    "POSITION_SIZING_BLOCKED": "Uygun işlem büyüklüğü oluşmadı",
    "PAPER_TRADE_OPENED": "Paper işlem açıldı",
    "WATCH": "İzlemeye alındı",
    "REJECT": "Aday elendi",
}

_EXIT_LABELS = {
    "VERIFIED": "Çıkış doğrulandı",
    "LIMITED": "Çıkış kısmen doğrulandı",
    "UNVERIFIED": "Henüz doğrulanmadı",
    "DEFERRED": "Doğrulama sırada",
}


def reason_label(value: Any) -> str:
    key = str(value or "").strip().upper()
    return _REASON_LABELS.get(
        key,
        "Karar kaydı mevcut",
    )


def exit_label(value: Any) -> str:
    key = str(value or "").strip().upper()
    return _EXIT_LABELS.get(
        key,
        "Henüz doğrulanmadı",
    )


def build_operations_payload(
    *,
    runtime_active: bool,
    watch: dict[str, Any],
    paper: dict[str, Any],
    decisions: list[dict[str, Any]],
    data_healthy: bool = True,
) -> dict[str, Any]:
    open_watch = int(watch.get("open") or 0)
    closed_watch = int(watch.get("closed") or 0)
    verified = int(watch.get("verified") or 0)
    limited = int(watch.get("limited") or 0)
    probed = int(watch.get("probed") or 0)

    paper_open = int(paper.get("open") or 0)
    paper_closed = int(paper.get("closed") or 0)

    if not runtime_active:
        system_state = "SAFE"
        system_label = "Sistem güvenli beklemede"
    elif not data_healthy:
        system_state = "DEGRADED"
        system_label = "Sistem sınırlı veriyle çalışıyor"
    else:
        system_state = "HEALTHY"
        system_label = "Sistem çalışıyor"

    if verified:
        watch_label = f"{verified} çıkış doğrulandı"
    elif probed:
        watch_label = "Çıkış doğrulamaları sürüyor"
    elif open_watch:
        watch_label = "İzlenen fırsatlar takip ediliyor"
    else:
        watch_label = "İzlenen fırsat yok"

    top_reason = None

    if decisions:
        top_reason = decisions[0]

    return {
        "system": {
            "state": system_state,
            "label": system_label,
        },
        "watch": {
            "open": open_watch,
            "closed": closed_watch,
            "verified": verified,
            "limited": limited,
            "probed": probed,
            "label": watch_label,
        },
        "paper": {
            "open": paper_open,
            "closed": paper_closed,
            "net_pnl_usdt": paper.get("net_pnl_usdt"),
        },
        "decisions": decisions,
        "main_reason": (
            {
                "label": reason_label(
                    top_reason.get("reason")
                ),
                "count": int(
                    top_reason.get("count") or 0
                ),
            }
            if top_reason
            else None
        ),
        "presentation": {
            "technical_details_hidden": True,
            "fabricated_values": False,
        },
    }


def build_vezir_context(
    operations: dict[str, Any],
) -> dict[str, Any]:
    return {
        "role": "OPERASYON_ANALISTI",
        "authority": "READ_ONLY",
        "operations": operations,
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
            "format": "ozet_neden_ne_yapmali",
        },
    }
