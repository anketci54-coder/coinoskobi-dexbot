from __future__ import annotations

from typing import Any
import unicodedata

_REASON_LABELS={"PLAN_BLOCKED":"İşlem şartları oluşmadı","POSITION_SIZING_BLOCKED":"Uygun işlem büyüklüğü oluşmadı","PAPER_TRADE_OPENED":"Paper işlem açıldı","WATCH":"İzlemeye alındı","REJECT":"Aday elendi"}
_EXIT_LABELS={"VERIFIED":"Çıkış doğrulandı","LIMITED":"Çıkış kısmen doğrulandı","UNVERIFIED":"Henüz doğrulanmadı","DEFERRED":"Doğrulama sırada"}

def reason_label(value:Any)->str:
    return _REASON_LABELS.get(str(value or '').strip().upper(),'Karar kaydı mevcut')

def exit_label(value:Any)->str:
    return _EXIT_LABELS.get(str(value or '').strip().upper(),'Henüz doğrulanmadı')

def build_operations_payload(*,runtime_active:bool,watch:dict[str,Any],paper:dict[str,Any],decisions:list[dict[str,Any]],data_healthy:bool=True)->dict[str,Any]:
    ow=int(watch.get('open') or 0); cw=int(watch.get('closed') or 0); v=int(watch.get('verified') or 0); l=int(watch.get('limited') or 0); p=int(watch.get('probed') or 0)
    po=int(paper.get('open') or 0); pc=int(paper.get('closed') or 0)
    if not runtime_active: ss,sl='SAFE','Sistem güvenli beklemede'
    elif not data_healthy: ss,sl='DEGRADED','Sistem sınırlı veriyle çalışıyor'
    else: ss,sl='HEALTHY','Sistem çalışıyor'
    wl=f'{v} çıkış doğrulandı' if v else ('Çıkış doğrulamaları sürüyor' if p else ('İzlenen fırsatlar takip ediliyor' if ow else 'İzlenen fırsat yok'))
    top=decisions[0] if decisions else None
    return {'system':{'state':ss,'label':sl},'watch':{'open':ow,'closed':cw,'verified':v,'limited':l,'probed':p,'label':wl},'paper':{'open':po,'closed':pc,'net_pnl_usdt':paper.get('net_pnl_usdt')},'decisions':decisions,'main_reason':({'label':reason_label(top.get('reason')),'count':int(top.get('count') or 0)} if top else None),'presentation':{'technical_details_hidden':True,'fabricated_values':False}}

def build_vezir_context(operations:dict[str,Any])->dict[str,Any]:
    return {'role':'OPERASYON_ANALISTI','authority':'READ_ONLY','operations':operations,'permissions':{'trade':False,'wallet':False,'signing':False,'database_write':False,'runtime_control':False,'deployment':False},'response_policy':{'technical_by_default':False,'fabricate_missing_data':False,'format':'ozet_neden_ne_yapmali'}}

def _vezir_norm(value:Any)->str:
    text=str(value or '').strip(); repl={'ı':'i','İ':'I','ş':'s','Ş':'S','ğ':'g','Ğ':'G','ü':'u','Ü':'U','ö':'o','Ö':'O','ç':'c','Ç':'C'}
    for a,b in repl.items(): text=text.replace(a,b)
    text=unicodedata.normalize('NFKD',text)
    return ' '.join(''.join(ch for ch in text if not unicodedata.combining(ch)).lower().split())

def _vezir_money(value:Any)->str:
    try: n=float(value)
    except (TypeError,ValueError): return 'veri yok'
    return f"{'+' if n>0 else ''}{n:.2f} USDT"

def _vezir_int(value:Any)->int:
    try:return int(value or 0)
    except (TypeError,ValueError):return 0

def answer_vezir_query(
    question: str,
    operations: dict[str, Any],
) -> dict[str, Any]:
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

    market = dict(
        operations.get("market")
        or {}
    )

    wallet = dict(
        operations.get("wallet")
        or {}
    )

    reason = operations.get(
        "main_reason"
    )

    ss = str(
        system.get("state")
        or "UNKNOWN"
    ).upper()

    sl = str(
        system.get("label")
        or "Sistem durumu bilinmiyor"
    )

    wo = _vezir_int(
        watch.get("open")
    )

    wv = _vezir_int(
        watch.get("verified")
    )

    wl = _vezir_int(
        watch.get("limited")
    )

    wp = _vezir_int(
        watch.get("probed")
    )

    po = _vezir_int(
        paper.get("open")
    )

    pc = _vezir_int(
        paper.get("closed")
    )

    pnl = paper.get(
        "net_pnl_usdt"
    )

    tech = any(
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

    if q in {
        "selam",
        "merhaba",
        "selamlar",
        "hey",
        "sa",
        "gunaydin",
        "iyi gunler",
        "iyi aksamlar",
    }:
        intent = "GREETING"
        answer = (
            "Selam. Radar, açık işlemler, risk, "
            "cüzdanlar veya haberlerin piyasa etkisine bakabiliriz."
        )

    elif any(
        marker in q
        for marker in (
            "nasilsin",
            "naber",
            "ne haber",
        )
    ):
        intent = "SMALLTALK"
        answer = (
            "İyiyim. Sistem verilerini takip ediyorum. "
            "İstersen şu anki fırsatları, açık işlemleri veya riskleri özetleyeyim."
        )

    elif any(
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

        if po:
            answer = (
                f"Şu anda {po} açık paper işlem var; "
                "sistem tamamen işlemsiz değil."
            )

        elif reason:
            answer = (
                "Açık paper işlem yok. "
                f"Son kararların ana nedeni: "
                f"{reason.get('label') or 'İşlem şartları oluşmadı'}."
            )

            count = _vezir_int(
                reason.get("count")
            )

            if count:
                answer += (
                    f" Bu durum {count} kayıtta görüldü."
                )

            if ss == "DEGRADED":
                answer += (
                    " Ayrıca sistem sınırlı veriyle çalışıyor; "
                    "bazı fırsatların teyidi gecikebilir."
                )

        elif ss == "DEGRADED":
            answer = (
                "Açık paper işlem yok. "
                "Sistem sınırlı veriyle çalışıyor; "
                "işlem şartlarının teyidi şu an zayıf."
            )

        else:
            answer = (
                "Açık paper işlem yok ve "
                "şu an bunu açıklayan yeterli güncel karar kaydı görünmüyor."
            )

    elif any(
        marker in q
        for marker in (
            "haber",
            "news",
            "listeleme",
            "airdrop",
            "ido",
            "ico",
        )
    ):
        intent = "NEWS_IMPACT"

        rows = (
            market.get("items")
            if isinstance(
                market.get("items"),
                list,
            )
            else []
        )

        parts = []

        for row in rows[:3]:
            if not isinstance(row, dict):
                continue

            title = str(
                row.get("title_tr")
                or "PİYASA"
            ).strip()

            scope = str(
                row.get("market_scope_tr")
                or "GENEL KRİPTO"
            ).strip()

            summary = str(
                row.get("summary_tr")
                or "Etki sınıflandırması yok."
            ).strip()

            recommendation = str(
                row.get("recommendation_tr")
                or "Teyit bekle."
            ).strip()

            try:
                score = int(
                    row.get(
                        "importance_score"
                    )
                    or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                score = 0

            item = (
                f"{title}"
                + (
                    f" [{score}/100]"
                    if score
                    else ""
                )
                + f". Etki alanı: {scope}. "
                + f"{summary} "
                + f"Ne yapmalı: {recommendation}"
            )

            parts.append(item)

        answer = (
            " | ".join(parts)
            if parts
            else (
                "Şu anda güvenilir biçimde yorumlanabilecek "
                "güncel haber etkisi görünmüyor."
            )
        )

    elif any(
        marker in q
        for marker in (
            "cuzdan",
            "cüzdan",
            "wallet",
            "balina",
        )
    ):
        intent = "WALLET"

        candidates = _vezir_int(
            wallet.get("candidates")
        )

        successful = _vezir_int(
            wallet.get("successful")
        )

        holdings = _vezir_int(
            wallet.get("holdings_wallets")
        )

        if wallet:
            answer = (
                f"{candidates} aday cüzdan var. "
                "Bu sayı başarı skoru değil; sistemin izlemeye aldığı farklı cüzdan sayısıdır. "
                f"{successful} cüzdan başarılı olarak doğrulanmış, "
                f"{holdings} cüzdan için holdings verisi bulunuyor. "
                "Detay ekranında her cüzdanın neden aday olduğunu, örneklem durumunu ve balina yönünü görebilirsin."
            )

        else:
            answer = (
                "Cüzdan sayısı tek başına kalite skoru değildir. "
                "Detay için CÜZDAN / BALİNA bölümündeki aday nedeni, başarı ve yön bilgisine bak."
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

        if ss == "DEGRADED":
            answer = (
                "Şu an en önemli risk veri akışının sınırlı olması. "
                "Bu, fırsat ve çıkış teyitlerinin gecikmesine neden olabilir."
            )

        elif ss == "SAFE":
            answer = (
                "Sistem güvenli beklemede. "
                "Yeni işlem yerine veri akışının normale dönmesini beklemek daha doğru."
            )

        elif po:
            answer = (
                f"Sistem sağlıklı görünüyor fakat {po} açık paper pozisyon var. "
                "En yakın risk, açık pozisyonlarda fiyatın girişten ve son zirveden uzaklaşmasıdır; "
                "SAT ekranındaki güncel satış önizlemesini takip et."
            )

        else:
            answer = (
                "Panel verilerinde şu anda öne çıkan kritik bir sistem riski görünmüyor."
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

        if wv:
            answer = (
                f"{wv} WATCH çıkışı doğrulanmış durumda. "
                "Bunlar geçmiş izleme sonucudur; yeni giriş için radarın güncel fiyat ve hareket teyidine bak."
            )

        elif wo:
            answer = (
                f"{wo} fırsat izleniyor. "
                "Henüz doğrulanmış çıkış sonucu yok; "
                "sadece aday sayısına değil hareket, likidite ve güncel fiyat davranışına bak."
            )

        else:
            answer = (
                "Şu anda aktif izlenen veya doğrulanmış bir fırsat görünmüyor."
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
            f"{wo} fırsat izleniyor. "
            f"{wp} kayıt için çıkış kontrolü yapılmış, "
            f"{wv} doğrulanmış çıkış"
        )

        if wl:
            answer += (
                f", {wl} kısmi doğrulama"
            )

        answer += (
            ". WATCH kayıtları gerçek paper işlemlerden ayrı öğrenme gözlemleridir."
        )

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
            f"Şu anda {po} açık paper işlem var. "
            f"{pc} işlem kapanmış. "
            f"Gerçekleşen toplam sonuç {_vezir_money(pnl)}."
        )

        if po:
            answer += (
                " Açık işlemlerde SAT butonuna basınca "
                "güncel server fiyatı, PNL, başa baş seviyesi ve kısa hareket rehberi gösterilir."
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

        answer = sl + "."

        if ss == "HEALTHY":
            answer += (
                " Paper radar çalışıyor; live işlem yetkisi kapalı."
            )

        elif ss == "DEGRADED":
            answer += (
                " İşlem ve fırsat yorumlarında eksik veri ihtimalini dikkate al."
            )

    else:
        intent = "GENERAL"

        answer = (
            f"{sl}. "
            f"{po} açık paper işlem var, "
            f"{pc} işlem kapanmış. "
            f"{wo} WATCH fırsatı izleniyor."
        )

        if po:
            answer += (
                " Öncelik açık pozisyonların güncel satış durumunu ve kısa fiyat hareketini izlemek."
            )

        elif ss == "DEGRADED":
            answer += (
                " Öncelik veri akışının toparlanmasını beklemek."
            )

        else:
            answer += (
                " Yeni fırsat için radarın hareket ve likidite teyidini izle."
            )

    technical = None

    if tech:
        if ss == "DEGRADED":
            technical = (
                "Teknik özet: RPC/provider veri sağlayıcı sağlığı sınırlı."
            )
        elif ss == "HEALTHY":
            technical = (
                "Teknik özet: RPC/provider veri sağlayıcı sağlığı normal."
            )
        else:
            technical = (
                "Teknik özet: runtime normal aktif durumda değil."
            )

    return {
        "answer": answer,
        "intent": intent,
        "authority": "READ_ONLY",
        "technical": technical,

        "evidence": {
            "system_state": ss,
            "watch_open": wo,
            "watch_verified": wv,
            "watch_limited": wl,
            "watch_probed": wp,
            "paper_open": po,
            "paper_closed": pc,
            "main_reason_available": bool(
                reason
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
