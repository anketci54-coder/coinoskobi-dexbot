from __future__ import annotations

from typing import Any
import unicodedata


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

_GREETING_WORDS = {
    "selam", "merhaba", "hey", "sa", "gunaydin", "iyi aksamlar",
    "iyi geceler", "nasilsin", "naber",
}


def reason_label(value: Any) -> str:
    key = str(value or "").strip().upper()
    return _REASON_LABELS.get(key, "Karar kaydı mevcut")


def exit_label(value: Any) -> str:
    key = str(value or "").strip().upper()
    return _EXIT_LABELS.get(key, "Henüz doğrulanmadı")


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
        data_state = "RUNTIME_INACTIVE"
        data_label = "Paper runtime aktif değil"
    elif not data_healthy:
        system_state = "DEGRADED"
        system_label = "Sistem veri sağlayıcı sorunu nedeniyle kısıtlı çalışıyor"
        data_state = "PROVIDER_DEGRADED"
        data_label = "RPC/provider veri akışı doğrulanamıyor"
    else:
        system_state = "HEALTHY"
        system_label = "Sistem çalışıyor"
        data_state = "HEALTHY"
        data_label = "Veri sağlayıcı erişimi doğrulandı"

    if verified:
        watch_label = f"{verified} çıkış doğrulandı"
    elif probed:
        watch_label = "Çıkış doğrulamaları sürüyor"
    elif open_watch:
        watch_label = "İzlenen fırsatlar takip ediliyor"
    else:
        watch_label = "İzlenen fırsat yok"

    top_reason = decisions[0] if decisions else None

    return {
        "system": {
            "state": system_state,
            "label": system_label,
            "data_state": data_state,
            "data_label": data_label,
            "provider_problem": bool(runtime_active and not data_healthy),
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
                "label": reason_label(top_reason.get("reason")),
                "count": int(top_reason.get("count") or 0),
            }
            if top_reason
            else None
        ),
        "presentation": {
            "technical_details_hidden": True,
            "fabricated_values": False,
        },
    }


def build_vezir_context(operations: dict[str, Any]) -> dict[str, Any]:
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


def _vezir_norm(value: Any) -> str:
    text = str(value or "").strip()
    replacements = {
        "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
        "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().split())


def _vezir_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "veri yok"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f} USDT"


def _vezir_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_greeting(q: str) -> bool:
    if q in _GREETING_WORDS:
        return True
    words = q.split()
    return len(words) <= 3 and any(word in _GREETING_WORDS for word in words)


def answer_vezir_query(
    question: str,
    operations: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic read-only Vezir response engine."""
    q = _vezir_norm(question)
    system = dict(operations.get("system") or {})
    watch = dict(operations.get("watch") or {})
    paper = dict(operations.get("paper") or {})
    main_reason = operations.get("main_reason")

    system_state = str(system.get("state") or "UNKNOWN").upper()
    system_label = str(system.get("label") or "Sistem durumu bilinmiyor")
    data_label = str(system.get("data_label") or "")
    provider_problem = bool(system.get("provider_problem"))

    watch_open = _vezir_int(watch.get("open"))
    watch_verified = _vezir_int(watch.get("verified"))
    watch_limited = _vezir_int(watch.get("limited"))
    watch_probed = _vezir_int(watch.get("probed"))
    paper_open = _vezir_int(paper.get("open"))
    paper_closed = _vezir_int(paper.get("closed"))
    pnl = paper.get("net_pnl_usdt")

    technical_requested = any(
        marker in q
        for marker in ("teknik", "detay", "rpc", "provider", "neden bozuk")
    )

    intent = "GENERAL"

    if _is_greeting(q):
        intent = "GREETING"
        answer = "Selam. Buradayım; sistemi, fırsatları, riskleri veya işlemleri sorabilirsin."

    elif any(marker in q for marker in (
        "neden islem acmadik", "neden islem yok", "niye islem acmadik",
        "neden almadik", "neden trade yok",
    )):
        intent = "WHY_NO_TRADE"
        if paper_open > 0:
            answer = f"Şu anda {paper_open} açık paper işlem var; sistem tamamen işlemsiz değil."
        elif provider_problem:
            answer = (
                "Açık paper işlem yok. RPC/provider veri akışında sorun var; "
                "bu yüzden bazı adayların güncel verisi ve işlem şartları güvenilir biçimde doğrulanamıyor."
            )
            if main_reason:
                reason = str(main_reason.get("label") or "İşlem şartları oluşmadı")
                count = _vezir_int(main_reason.get("count"))
                answer += f" Son kararların ana nedeni: {reason}"
                if count:
                    answer += f" ({count} kayıt)"
                answer += "."
        elif main_reason:
            reason = str(main_reason.get("label") or "İşlem şartları oluşmadı")
            count = _vezir_int(main_reason.get("count"))
            answer = f"Açık paper işlem yok. Son kararların ana nedeni: {reason}."
            if count:
                answer += f" Bu durum {count} kayıtta görüldü."
        elif system_state == "DEGRADED":
            answer = "Açık paper işlem yok. Veri akışı sağlıklı olmadığı için şartlar güvenilir biçimde doğrulanamıyor."
        else:
            answer = "Açık paper işlem yok. Bunu açıklayacak yeterli güncel karar nedeni görünmüyor."

    elif any(marker in q for marker in (
        "risk", "sorun", "tehlike", "problem", "provider", "rpc",
    )):
        intent = "RISK"
        if provider_problem:
            answer = (
                "Şu an en önemli sorun RPC/provider veri akışı. Paper runtime aktif olsa bile "
                "universe discovery ve güncel doğrulama eksik kalabilir."
            )
        elif system_state == "SAFE":
            answer = "Sistem güvenli beklemede; yeni işlem değerlendirmesi normal ilerlemiyor."
        elif watch_open > 0 and watch_verified == 0:
            answer = (
                f"{watch_open} fırsat izleniyor ancak henüz doğrulanmış WATCH çıkışı yok. "
                "En önemli belirsizlik çıkış gerçekleşebilirliği."
            )
        else:
            answer = "Şu anda panel verilerinde öne çıkan kritik bir sistem riski görünmüyor."

    elif any(marker in q for marker in ("firsat", "aday", "en iyi", "guclu")):
        intent = "OPPORTUNITY"
        if provider_problem:
            answer = (
                "Provider veri akışı sağlıklı olmadığı için şu anda tek bir adayı güvenilir biçimde "
                "en güçlü fırsat ilan etmiyorum."
            )
        elif watch_verified > 0:
            answer = f"{watch_verified} WATCH çıkışı doğrulanmış durumda; en güçlü doğrulanmış kanıt bunlarda."
        elif watch_open > 0:
            answer = f"{watch_open} fırsat izleniyor; henüz doğrulanmış çıkış olmadığı için tek aday seçmiyorum."
        else:
            answer = "Şu anda doğrulanmış veya aktif izlenen bir fırsat görünmüyor."

    elif any(marker in q for marker in ("watch", "izlenen", "izleme", "probe")):
        intent = "WATCH"
        answer = (
            f"{watch_open} fırsat izleniyor. {watch_probed} kayıt için çıkış kontrolü yapılmış, "
            f"{watch_verified} çıkış doğrulanmış"
        )
        if watch_limited:
            answer += f", {watch_limited} kayıt kısmen doğrulanmış"
        answer += "."
        if provider_problem:
            answer += " Provider veri sorunu çıkış doğrulamalarını geciktirebilir."

    elif any(marker in q for marker in ("islem", "pozisyon", "paper", "pnl", "kar zarar")):
        intent = "POSITIONS"
        answer = (
            f"Şu anda {paper_open} açık paper işlem var. {paper_closed} işlem kapanmış. "
            f"Gerçekleşen toplam sonuç {_vezir_money(pnl)}."
        )
        if provider_problem:
            answer += " Provider veri akışı şu anda sorunlu; yeni giriş değerlendirmeleri etkilenebilir."

    elif any(marker in q for marker in ("sistem", "durum", "saglik", "calisiyor mu")):
        intent = "SYSTEM"
        answer = system_label + "."
        if provider_problem:
            answer += " Paper runtime açık ancak RPC/provider veri akışı doğrulanamıyor."

    else:
        intent = "GENERAL"
        answer = (
            f"{system_label}. {watch_open} fırsat izleniyor, {paper_open} açık paper işlem var. "
            f"Gerçekleşen sonuç {_vezir_money(pnl)}."
        )
        if provider_problem:
            answer += " RPC/provider veri akışında sorun var."
        if main_reason:
            label = str(main_reason.get("label") or "")
            if label:
                answer += f" Son kararların ana durumu: {label}."

    technical_note = None
    if technical_requested:
        if provider_problem:
            technical_note = (
                "Teknik özet: RPC/provider sağlık kontrolü kullanılabilir veri sağlayıcıyı "
                "doğrulayamıyor; universe discovery DEGRADED çalışabilir."
            )
        elif system_state == "HEALTHY":
            technical_note = "Teknik özet: en az bir kullanılabilir RPC/veri sağlayıcı doğrulandı."
        else:
            technical_note = "Teknik özet: runtime normal aktif durumda değil."

    return {
        "answer": answer,
        "intent": intent,
        "authority": "READ_ONLY",
        "technical": technical_note,
        "evidence": {
            "system_state": system_state,
            "provider_problem": provider_problem,
            "data_label": data_label or None,
            "watch_open": watch_open,
            "watch_verified": watch_verified,
            "watch_limited": watch_limited,
            "watch_probed": watch_probed,
            "paper_open": paper_open,
            "paper_closed": paper_closed,
            "main_reason_available": bool(main_reason),
        },
        "permissions": {
            "trade": False,
            "wallet": False,
            "signing": False,
            "database_write": False,
            "runtime_control": False,
            "deployment": False,
        },
    }
