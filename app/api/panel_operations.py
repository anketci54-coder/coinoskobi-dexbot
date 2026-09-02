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


def _vezir_norm(value: Any) -> str:
    text = str(value or "").strip()

    replacements = {
        "ı": "i",
        "İ": "I",
        "ş": "s",
        "Ş": "S",
        "ğ": "g",
        "Ğ": "G",
        "ü": "u",
        "Ü": "U",
        "ö": "o",
        "Ö": "O",
        "ç": "c",
        "Ç": "C",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        ch
        for ch in text
        if not unicodedata.combining(ch)
    )

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


def answer_vezir_query(
    question: str,
    operations: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic read-only Vezir response engine.

    It only interprets the bounded operations payload supplied by
    the panel backend. It cannot query arbitrary SQL, mutate state,
    control services, trade, sign or access wallet authority.
    """

    q = _vezir_norm(question)

    system = dict(
        operations.get("system")
        or {}
    )

    watch = dict(
        operations.get("watch")
        or {}
    )

    paper = dict(
        operations.get("paper")
        or {}
    )

    main_reason = operations.get(
        "main_reason"
    )

    system_state = str(
        system.get("state")
        or "UNKNOWN"
    ).upper()

    system_label = str(
        system.get("label")
        or "Sistem durumu bilinmiyor"
    )

    watch_open = _vezir_int(
        watch.get("open")
    )

    watch_verified = _vezir_int(
        watch.get("verified")
    )

    watch_limited = _vezir_int(
        watch.get("limited")
    )

    watch_probed = _vezir_int(
        watch.get("probed")
    )

    paper_open = _vezir_int(
        paper.get("open")
    )

    paper_closed = _vezir_int(
        paper.get("closed")
    )

    pnl = paper.get(
        "net_pnl_usdt"
    )

    technical_requested = any(
        marker in q
        for marker in (
            "teknik",
            "detay",
            "rpc",
            "provider",
            "neden bozuk",
        )
    )

    intent = "GENERAL"
    answer = ""

    if any(
        marker in q
        for marker in (
            "neden islem acmadik",
            "neden islem yok",
            "niye islem acmadik",
            "neden almadik",
            "neden trade yok",
        )
    ):
        intent = "WHY_NO_TRADE"

        if paper_open > 0:
            answer = (
                f"Şu anda {paper_open} açık paper işlem var. "
                "Bu nedenle sistem tamamen işlemsiz değil."
            )

        elif main_reason:
            reason = str(
                main_reason.get("label")
                or "İşlem şartları oluşmadı"
            )

            count = _vezir_int(
                main_reason.get("count")
            )

            answer = (
                f"Açık paper işlem yok. "
                f"Son karar kayıtlarında ana neden: {reason}."
            )

            if count:
                answer += (
                    f" Bu durum {count} kayıtta görüldü."
                )

            if system_state == "DEGRADED":
                answer += (
                    " Ayrıca sistem şu anda sınırlı veriyle çalışıyor."
                )

        elif system_state == "DEGRADED":
            answer = (
                "Açık paper işlem yok. "
                "Sistem şu anda sınırlı veriyle çalışıyor; "
                "bu nedenle işlem şartlarının doğrulanması zayıflamış olabilir. "
                "Kesin karar nedeni için yeterli güncel kayıt yok."
            )

        else:
            answer = (
                "Açık paper işlem yok. "
                "Bunu açıklayacak yeterli güncel karar nedeni görünmüyor."
            )

    elif any(
        marker in q
        for marker in (
            "risk",
            "sorun",
            "tehlike",
            "problem",
        )
    ):
        intent = "RISK"

        if system_state == "DEGRADED":
            answer = (
                "Şu an en önemli risk veri akışının sınırlı olması. "
                "Sistem çalışıyor ancak bazı fırsatları doğrulamakta zorlanabilir."
            )

        elif system_state == "SAFE":
            answer = (
                "Sistem güvenli beklemede. "
                "Yeni işlem değerlendirmesi normal şekilde ilerlemiyor."
            )

        elif watch_open > 0 and watch_verified == 0:
            answer = (
                f"{watch_open} fırsat izleniyor ancak henüz doğrulanmış "
                "WATCH çıkışı yok. En önemli belirsizlik çıkış gerçekleşebilirliği."
            )

        else:
            answer = (
                "Şu anda panel verilerinde öne çıkan kritik bir sistem riski görünmüyor."
            )

    elif any(
        marker in q
        for marker in (
            "firsat",
            "aday",
            "en iyi",
            "guclu",
        )
    ):
        intent = "OPPORTUNITY"

        if watch_verified > 0:
            answer = (
                f"{watch_verified} WATCH çıkışı doğrulanmış durumda. "
                "Bunlar şu anda en güçlü doğrulanmış fırsat kanıtını oluşturuyor."
            )

        elif watch_open > 0:
            answer = (
                f"{watch_open} fırsat izleniyor. "
                "Henüz doğrulanmış çıkış olmadığı için tek bir adayı "
                "kesin en güçlü fırsat olarak ilan edemem."
            )

        else:
            answer = (
                "Şu anda doğrulanmış veya aktif izlenen bir fırsat görünmüyor."
            )

    elif any(
        marker in q
        for marker in (
            "watch",
            "izlenen",
            "izleme",
            "probe",
        )
    ):
        intent = "WATCH"

        answer = (
            f"{watch_open} fırsat izleniyor. "
            f"{watch_probed} kayıt için çıkış kontrolü yapılmış, "
            f"{watch_verified} çıkış doğrulanmış"
        )

        if watch_limited:
            answer += (
                f", {watch_limited} kayıt kısmen doğrulanmış"
            )

        answer += "."

    elif any(
        marker in q
        for marker in (
            "islem",
            "pozisyon",
            "paper",
            "pnl",
            "kar zarar",
        )
    ):
        intent = "POSITIONS"

        answer = (
            f"Şu anda {paper_open} açık paper işlem var. "
            f"{paper_closed} işlem kapanmış. "
            f"Gerçekleşen toplam sonuç {_vezir_money(pnl)}."
        )

    elif any(
        marker in q
        for marker in (
            "sistem",
            "durum",
            "saglik",
            "calisiyor mu",
        )
    ):
        intent = "SYSTEM"

        answer = system_label + "."

        if system_state == "DEGRADED":
            answer += (
                " Ana işlevler açık ancak veri doğrulama kapasitesi sınırlı."
            )

    else:
        intent = "GENERAL"

        answer = (
            f"{system_label}. "
            f"{watch_open} fırsat izleniyor, "
            f"{paper_open} açık paper işlem var. "
            f"Gerçekleşen sonuç {_vezir_money(pnl)}."
        )

        if main_reason:
            label = str(
                main_reason.get("label")
                or ""
            )

            if label:
                answer += (
                    f" Son kararların ana durumu: {label}."
                )

    technical_note = None

    if technical_requested:
        if system_state == "DEGRADED":
            technical_note = (
                "Teknik özet: panelin veri sağlık kontrolü "
                "en az bir kullanılabilir RPC sağlayıcı doğrulayamadı."
            )
        elif system_state == "HEALTHY":
            technical_note = (
                "Teknik özet: panel en az bir kullanılabilir "
                "veri sağlayıcı doğruladı."
            )
        else:
            technical_note = (
                "Teknik özet: runtime normal aktif durumda değil."
            )

    return {
        "answer": answer,
        "intent": intent,
        "authority": "READ_ONLY",
        "technical": technical_note,
        "evidence": {
            "system_state": system_state,
            "watch_open": watch_open,
            "watch_verified": watch_verified,
            "watch_limited": watch_limited,
            "watch_probed": watch_probed,
            "paper_open": paper_open,
            "paper_closed": paper_closed,
            "main_reason_available": bool(
                main_reason
            ),
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
