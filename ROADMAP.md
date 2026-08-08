# COINOSKOBI DEXBOT — ROADMAP

> Bu dosya projenin tam yol haritasıdır.
> Her faz tamamlandığında ilgili maddenin yanına `✅ DONE` yazılır.
> Yeni bir sohbet açıldığında bu dosya okunarak kaldığımız yer bulunur.

---

## ÇALIŞMA DÜZENİ

```
1. Her faz için bir Problem Statement hazırlanır
2. GitHub Copilot Coding Agent'a verilir
3. Agent bir Pull Request oluşturur
4. PR incelenir ve merge edilir
5. Bu dosyada ilgili adım ✅ DONE olarak işaretlenir
6. Sonraki faza geçilir
```

---

## KURALLAR

- Yama yok. Geçici script yok. Sadece çalışan dosyalar.
- Gereksiz kod, ölü kod, kullanılmayan import → silinir.
- Her PR tek bir fazı kapsar. Karışık PR kabul edilmez.
- Dosya silinecekse PR içinde silinir, arta kalmaz.
- Her değişiklik için gerekçe vardır.

---

## PROJE DURUMU

**Şu anki faz:** FAZ 0
**Son güncelleme:** 2026-08-07
**Genel ilerleme:** 0 / 6 faz tamamlandı

---

## FAZ 0 — KRİTİK BUGFIX + TEMİZLİK

> Bot şu an fiilen çalışmıyor. Bu faz olmadan hiçbir şey işe yaramaz.

### Neden Kritik

- `gecko_pool_cache` tablosunda `price_usd` sütunu yok
- `CachePrice.get_price()` her çağrıda `OperationalError` fırlatıyor
- `main.py` bunu sessizce yakalayıp `price = 0.0` yapıyor
- Sonuç: tüm adaylar reject ediliyor, paper trading fiilen çalışmıyor
- `ALLOWED_DEX` filtresi tanımlı ama hiçbir yerde uygulanmıyor
- `requirements.txt` içinde 8 kullanılmayan paket var, sürüm pinlemesi yok
- `app/scanner/pairs.py` pipeline'a bağlı değil — orphan script
- `app/paper/portfolio.py` manager.py ile tamamen aynı SQL bloğu — duplicate

### Yapılacaklar

- [ ] `app/cache/gecko_cache.py` → `price_usd` sütunu ekle, `replace()` güncelle
- [ ] `app/scanner/gecko_scanner.py` → `price_usd` cache'e yazılsın, `ALLOWED_DEX` filtresi uygula
- [ ] `app/filter/cache_filter.py` → `ALLOWED_DEX` filtresi uygula
- [ ] `app/paper/cache_price.py` → uyumluluk doğrulaması
- [ ] `requirements.txt` → 8 kullanılmayan paket kaldır, sürüm pinle
- [ ] `app/scanner/pairs.py` → **SİL** (orphan, pipeline'a bağlı değil)
- [ ] `app/paper/portfolio.py` → **SİL** (manager.py ile duplicate)

### Durum

⏳ Bekliyor

---

## FAZ 1 — TEMEL ALTYAPI

> Botun gerçek anlamda bot gibi davranması için minimum gereksinimler.

### Yapılacaklar

- [ ] `app/core/logger.py` → loguru yapılandırması, rotating file log
- [ ] `app/core/runner.py` → ana döngü (her 5 dk scan, her 1 dk pozisyon güncelle)
- [ ] `app/paper/database.py` → WAL mode, tek connection, singleton
- [ ] `app/config/paper.py` → magic number'ları buraya taşı (TP, SL, gas, amount)
- [ ] `app/config/contracts.py` → factory.py + routers.py + tokens.py birleştir
- [ ] `main.py` → config'den oku, logging ekle, duplicate PaperDatabase kaldır
- [ ] `app/config/factory.py` → **SİL** (contracts.py'ye taşındı)
- [ ] `app/config/routers.py` → **SİL** (contracts.py'ye taşındı)
- [ ] `app/config/tokens.py` → **SİL** (contracts.py'ye taşındı)

### Durum

⏳ Bekliyor

---

## FAZ 2 — PERFORMANS VE GERÇEK ZAMANLILIK

> Senkron RPC çağrıları pipeline'ı yavaşlatıyor. Portfolio SQL 3 yerde duplicate.

### Yapılacaklar

- [ ] `app/analyzer/token.py` → async, class yapısına geçiş
- [ ] `app/analyzer/pair.py` → async, modül-seviyesi RPC nesnesini kaldır
- [ ] `app/risk/bytecode.py` → async
- [ ] `app/core/runner.py` → asyncio.gather ile paralel RPC çağrıları
- [ ] `app/paper/portfolio.py` → `PortfolioService` sınıfı (tek SQL kaynağı)
- [ ] `app/paper/manager.py` → PortfolioService kullan, duplicate SQL kaldır
- [ ] `app/api/server.py` → PortfolioService kullan, raw db.conn kaldır
- [ ] `requirements.txt` → `aiohttp` ekle

### Durum

⏳ Bekliyor

---

## FAZ 3 — STRATEJİ VE RİSK GÜÇLENDİRME

> Strateji kör. Honeypot tespiti yok. Position sizing sabit.

### Yapılacaklar

- [ ] `app/risk/honeypot.py` → honeypot.is API entegrasyonu (ücretsiz)
- [ ] `app/config/strategy.py` → SCORE_BUY, SCORE_WATCH, MAX_BUY_TAX config'e taşı
- [ ] `app/strategy/engine.py` → honeypot sinyali ekle, config-driven eşikler
- [ ] `app/filter/cache_filter.py` → pool age filtresi aktive et (MAX_POOL_AGE_HOURS)
- [ ] `app/config/paper.py` → MAX_OPEN_POSITIONS, MAX_TOTAL_EXPOSURE_BNB ekle
- [ ] `main.py` → exposure limiti kontrolü ekle

### Durum

⏳ Bekliyor

---

## FAZ 4 — API VE DEPLOYMENT

> FastAPI güvensiz. Dockerfile boş. Deployment yok.

### Yapılacaklar

- [ ] `app/api/server.py` → Bearer token auth, /health endpoint, /stats endpoint
- [ ] `Dockerfile` → doldur
- [ ] `docker-compose.yml` → bot + api servisleri
- [ ] `.env.example` → yeni değişkenleri ekle (API_KEY, TELEGRAM_TOKEN vb.)

### Durum

⏳ Bekliyor

---

## FAZ 5 — METRİKLER VE ALERTLER

> Bot sessizce çalışıyor. Ne olduğunu bilmiyorsun.

### Yapılacaklar

- [ ] `app/analytics/metrics.py` → win rate, avg ROI, max drawdown, Sharpe
- [ ] `app/alerts/telegram.py` → paper buy / TP / SL / hata alertleri
- [ ] `app/api/server.py` → /metrics endpoint ekle
- [ ] `.env.example` → TELEGRAM_TOKEN, TELEGRAM_CHAT_ID ekle

### Durum

⏳ Bekliyor

---

## FAZ 6 — LIVE TRADING HAZIRLIĞI

> Paper trading sonuçları en az 2 hafta pozitif olmadan bu faza geçilmez.

### Yapılacaklar

- [ ] `app/execution/swap.py` → buy/sell transaction engine
- [ ] `app/execution/guard.py` → balance kontrolü, emergency stop
- [ ] `app/config/settings.py` → TRADING_MODE = paper | live
- [ ] `app/chains/bsc.py` → 48.club private RPC desteği (MEV koruması)
- [ ] `.env.example` → TRADING_MODE, EMERGENCY_STOP ekle

### Durum

⏳ Bekliyor

---

## DOSYA HARİTASI (Hedef Mimari)

```
coinoskobi-dexbot/
├── main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── ROADMAP.md
├── ROADMAP.json
├── data/
├── logs/
└── app/
    ├── __init__.py
    ├── core/
    │   ├── logger.py        ← FAZ 1
    │   └── runner.py        ← FAZ 1
    ├── api/
    │   ├── __init__.py
    │   └── server.py
    ├── alerts/
    │   └── telegram.py      ← FAZ 5
    ├── analytics/
    │   └── metrics.py       ← FAZ 5
    ├── analyzer/
    │   ├── pair.py
    │   └── token.py
    ├── cache/
    │   └── gecko_cache.py
    ├── chains/
    │   ├── __init__.py
    │   └── bsc.py
    ├── config/
    │   ├── __init__.py
    │   ├── abis/
    │   ├── contracts.py     ← FAZ 1 (factory+routers+tokens birleşti)
    │   ├── paper.py         ← FAZ 1
    │   ├── scanner.py
    │   ├── settings.py
    │   └── strategy.py      ← FAZ 3
    ├── dex/
    │   ├── __init__.py
    │   ├── pancake.py
    │   └── quote.py
    ├── execution/
    │   ├── swap.py          ← FAZ 6
    │   └── guard.py         ← FAZ 6
    ├── filter/
    │   └── cache_filter.py
    ├── paper/
    │   ├── cache_price.py
    │   ├── database.py
    │   ├── manager.py
    │   └── portfolio.py     ← FAZ 2'de PortfolioService olarak yeniden yazılır
    ├── risk/
    │   ├── __init__.py
    │   ├── bytecode.py
    │   └── honeypot.py      ← FAZ 3
    ├── scanner/
    │   ├── __init__.py
    │   ├── gecko_scanner.py
    │   └── update_gecko_cache.py
    └── strategy/
        ├── __init__.py
        └── engine.py
```

---

## SILINECEK DOSYALAR (Toplam)

| Dosya | Faz | Neden |
|---|---|---|
| `app/scanner/pairs.py` | FAZ 0 | Orphan script, pipeline'a bağlı değil |
| `app/paper/portfolio.py` | FAZ 0 | manager.py ile duplicate SQL |
| `app/config/factory.py` | FAZ 1 | contracts.py'ye taşınacak |
| `app/config/routers.py` | FAZ 1 | contracts.py'ye taşınacak |
| `app/config/tokens.py` | FAZ 1 | contracts.py'ye taşınacak |

---

## MALİYET TABLOSU

| Bileşen | Seçenek | Maliyet |
|---|---|---|
| RPC (şimdi) | Ankr Free / QuickNode Free | $0 |
| RPC (live) | 48.club private | $0 |
| Hosting (şimdi) | Oracle Cloud Free Tier | $0 |
| Hosting (live) | Hetzner CX11 | ~$5/ay |
| Fiyat verisi | GeckoTerminal REST | $0 |
| Honeypot API | honeypot.is | $0 |
| Alert | Telegram Bot | $0 |

---

*Bu dosya her faz sonunda güncellenir.*

## Phase 1

Status: ✅ COMPLETED
