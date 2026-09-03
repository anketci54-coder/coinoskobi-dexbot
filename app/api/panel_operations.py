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

def answer_vezir_query(question:str,operations:dict[str,Any])->dict[str,Any]:
    q=_vezir_norm(question); system=dict(operations.get('system') or {}); watch=dict(operations.get('watch') or {}); paper=dict(operations.get('paper') or {}); reason=operations.get('main_reason')
    ss=str(system.get('state') or 'UNKNOWN').upper(); sl=str(system.get('label') or 'Sistem durumu bilinmiyor'); wo=_vezir_int(watch.get('open')); wv=_vezir_int(watch.get('verified')); wl=_vezir_int(watch.get('limited')); wp=_vezir_int(watch.get('probed')); po=_vezir_int(paper.get('open')); pc=_vezir_int(paper.get('closed')); pnl=paper.get('net_pnl_usdt')
    tech=any(x in q for x in ('teknik','detay','rpc','provider','neden bozuk')); intent='GENERAL'
    if q in {'selam','merhaba','selamlar','hey','sa','gunaydin','iyi gunler','iyi aksamlar'}:
        intent='GREETING'; answer='Selam. Buradayım. Radar, işlemler, risk veya sistemle ilgili neye bakmamı istersin?'
    elif any(x in q for x in ('nasilsin','naber','ne haber')):
        intent='SMALLTALK'; answer='İyiyim, sistem verilerini izliyorum. İstersen radarın durumuna veya neden işlem açılmadığına bakalım.'
    elif any(x in q for x in ('neden islem acmadik','neden islem yok','niye islem acmadik','neden almadik','neden trade yok')):
        intent='WHY_NO_TRADE'
        if po: answer=f'Şu anda {po} açık paper işlem var. Sistem tamamen işlemsiz değil.'
        elif reason:
            answer=f"Açık paper işlem yok. Son karar kayıtlarında ana neden: {reason.get('label') or 'İşlem şartları oluşmadı'}."; c=_vezir_int(reason.get('count')); answer+=f' Bu durum {c} kayıtta görüldü.' if c else ''; answer+=' Sistem şu anda sınırlı veriyle çalışıyor.' if ss=='DEGRADED' else ''
        elif ss=='DEGRADED': answer='Açık paper işlem yok. Sistem sınırlı veriyle çalışıyor; işlem şartlarının doğrulanması zayıflamış olabilir. Kesin karar nedeni için yeterli güncel kayıt yok.'
        else: answer='Açık paper işlem yok. Bunu açıklayacak yeterli güncel karar nedeni görünmüyor.'
    elif any(x in q for x in ('risk','sorun','tehlike','problem')):
        intent='RISK'; answer='Şu an en önemli risk veri akışının sınırlı olması.' if ss=='DEGRADED' else ('Sistem güvenli beklemede.' if ss=='SAFE' else 'Şu anda panel verilerinde öne çıkan kritik bir sistem riski görünmüyor.')
    elif any(x in q for x in ('firsat','aday','en iyi','guclu')):
        intent='OPPORTUNITY'; answer=f'{wv} WATCH çıkışı doğrulanmış durumda.' if wv else (f'{wo} fırsat izleniyor; henüz doğrulanmış çıkış yok.' if wo else 'Şu anda doğrulanmış veya aktif izlenen bir fırsat görünmüyor.')
    elif any(x in q for x in ('watch','izlenen','izleme','probe')):
        intent='WATCH'; answer=f'{wo} fırsat izleniyor. {wp} kayıt için çıkış kontrolü yapılmış, {wv} doğrulanmış çıkış'; answer+=f', {wl} kısmi doğrulama' if wl else ''; answer+='.'
    elif any(x in q for x in ('islem','pozisyon','paper','pnl','kar zarar')):
        intent='POSITIONS'; answer=f'Şu anda {po} açık paper işlem var. {pc} işlem kapanmış. Gerçekleşen toplam sonuç {_vezir_money(pnl)}.'
    elif any(x in q for x in ('sistem','durum','saglik','calisiyor mu')):
        intent='SYSTEM'; answer=sl+'.'
    else:
        answer='Sorunu mevcut operasyon verisinden güvenilir biçimde yanıtlayamıyorum. Radar, işlem, risk veya sistem durumunu sorabilirsin.'
    technical=None
    if tech: technical='Teknik özet: RPC/provider veri sağlayıcı sağlığı sınırlı.' if ss=='DEGRADED' else ('Teknik özet: RPC/provider veri sağlayıcı sağlığı normal.' if ss=='HEALTHY' else 'Teknik özet: runtime normal aktif durumda değil.')
    return {'answer':answer,'intent':intent,'authority':'READ_ONLY','technical':technical,'evidence':{'system_state':ss,'watch_open':wo,'watch_verified':wv,'watch_limited':wl,'watch_probed':wp,'paper_open':po,'paper_closed':pc,'main_reason_available':bool(reason)},'permissions':{'trade':False,'wallet':False,'signing':False,'database_write':False,'runtime_control':False,'deployment':False}}
