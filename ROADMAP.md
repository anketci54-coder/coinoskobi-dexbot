# COINOSKOBI DEXBOT — ROADMAP

> Bu dosya projenin resmi geliştirme planıdır.
> Her faz tamamlandığında yalnızca ilgili maddeler işaretlenir.
> Faz dışı geliştirme yapılmaz.

---

# ÇALIŞMA AKIŞI

1. Problem Statement
2. Kod
3. Compile
4. Import
5. Test
6. Smoke Test
7. Commit
8. Push
9. Roadmap Güncelle
10. Final Audit

Hiçbir faz bu 10 adım tamamlanmadan kapanmaz.

---

# KURALLAR

- Geçici script yok.
- Yama yok.
- Duplicate kod yok.
- Kullanılmayan dosya yok.
- Kullanılmayan import yok.
- Bir commit = Bir amaç.
- Bir PR = Bir faz.

---

# PROJE DURUMU

Current Phase : PHASE 2
Next Phase : PHASE 3

Progress

- Phase 0 : ✅
- Phase 1 : ✅
- Phase 2 : 🚧
- Phase 3 : ⏳
- Phase 4 : ⏳
- Phase 5 : ⏳
- Phase 6 : ⏳
- Phase 7 : ⏳
- Phase 8 : ⏳
- Phase 9 : ⏳
- Phase 10 : ⏳
- Phase 11 : ⏳
- Phase 12 : ⏳
- Phase 13 : ⏳
- Phase 14 : ⏳
- Phase 15 : ⏳

---

# PHASE 0 — Critical Bug Fixes

Amaç

Botun gerçekten çalışır hale gelmesi.

## Yapılacaklar

- [x] gecko_pool_cache → price_usd desteği
- [x] CachePrice uyumluluğu
- [x] ALLOWED_DEX filtresi
- [x] requirements.txt temizliği
- [x] app/scanner/pairs.py sil
- [x] duplicate portfolio kaldır

Status

✅ Completed

---

# PHASE 1 — Core Infrastructure

Amaç

Temiz ve sürdürülebilir altyapı.

## Yapılacaklar

- [x] app/core/logger.py
- [x] app/core/runner.py
- [x] app/paper/database.py
    - WAL mode ✅
    - singleton ✅
- [x] app/config/trading.py
- [x] app/config/contracts.py
- [x] main.py sadeleştirme
- [x] factory.py kaldır
- [x] routers.py kaldır
- [x] tokens.py kaldır

Status

✅ Completed

---

# PHASE 2 — Performance

Amaç

Pipeline hızlandırılması.

Ana prensip

Ölçmeden optimizasyon yapılmaz.
CPU tarafında zaten hızlı olan kod gereksiz yere yeniden yazılmaz.
Öncelik dış ağ / RPC gecikmesi, tekrar çağrılar ve paralel çalışmadır.

## Başlangıç Baseline

- [x] Compile PASS
- [x] Import smoke PASS
- [x] 36/36 test PASS
- [x] Clean venv 36/36 test PASS
- [x] DB integrity / quick check PASS
- [x] Scanner unit testi dış ağdan ayrıldı
- [x] GeckoTerminal live smoke PASS
- [x] Cache → Filter baseline ölçüldü
- [x] Filter micro benchmark ölçüldü
- [x] Strategy micro benchmark ölçüldü
- [x] Synthetic Pipeline E2E ölçüldü
- [x] Cycle isolation doğrulandı
- [ ] Token / Pair / Risk gerçek RPC latency baseline
- [ ] Sequential analyzer chain latency baseline

## Uygulama Sırası

### PHASE 2A — RPC Performance Baseline

- [ ] token analyzer RPC süreleri
- [ ] pair analyzer RPC süreleri
- [ ] risk analyzer RPC süreleri
- [ ] sequential analyzer toplam süre
- [ ] tekrar RPC çağrılarını tespit et
- [ ] mevcut cache reuse imkanlarını ölç
- [ ] performans hedeflerini belirle

Kural

Phase 2B, gerçek RPC darboğazı ölçülmeden başlamaz.

### PHASE 2B — Async Analyzer Contracts

- [ ] analyzer/token async
- [ ] analyzer/pair async
- [ ] risk/bytecode async
- [ ] mevcut sync sözleşme davranışını koru
- [ ] success / error / data sözleşmesini koru
- [ ] UNKNOWN fail-safe davranışını koru
- [ ] analyzer timeout politikası

Kural

Async dönüşüm trade/risk karar anlamını değiştiremez.

### PHASE 2C — Parallel RPC Orchestration

- [ ] Runner parallel RPC
- [ ] Token / Pair / Risk bağımsız çağrılarını paralel çalıştır
- [ ] bounded concurrency
- [ ] tek analyzer hatası diğerlerini düşürmesin
- [ ] external RPC rate-limit koruması
- [ ] sequential vs parallel benchmark

Kural

Sınırsız concurrency yok.
Tek token hatası diğer token fırsatlarını durduramaz.

### PHASE 2D — Scanner HTTP Performance

- [ ] aiohttp
- [ ] GeckoTerminal async HTTP
- [ ] HTTP timeout politikası
- [ ] 429 rate-limit davranışı
- [ ] retry / backoff sınırları
- [ ] scanner unit testleri tamamen offline kalacak
- [ ] live smoke ayrı tutulacak

Kural

Canlı API erişimi unit test suite içine geri alınmaz.

### PHASE 2E — Paper / Portfolio Performance

- [ ] PortfolioService
- [ ] Manager refactor
- [ ] gereksiz DB sorgularını tespit et
- [ ] paper position processing benchmark
- [ ] WAL / singleton davranışını koru
- [ ] paper trade sonuç sözleşmesini koru

Kural

Paper engine doğruluğu hız uğruna değiştirilemez.

### PHASE 2F — API Performance Refactor

- [ ] API refactor
- [ ] API yalnız aktif ihtiyaç varsa optimize edilir
- [ ] gereksiz framework / dependency eklenmez
- [ ] Phase 4 deployment sorumlulukları Phase 2'ye çekilmez

Kural

Phase 2 yalnız performans kapsamındadır.
Auth / deployment / live API işleri Phase 4 kapsamıdır.

## Performans Güvenlik Sınırları

- [ ] Live trading yok
- [ ] Wallet signing yok
- [ ] Private key kullanımı yok
- [ ] Trade authority değişikliği yok
- [ ] Strategy threshold değişikliği yok
- [ ] Risk skor mantığı değişikliği yok
- [ ] Fail-safe UNKNOWN davranışı korunacak
- [ ] MAX_RPC_CANDIDATES korunacak
- [ ] External rate-limit dikkate alınacak
- [ ] Her optimizasyon sonrası full test çalışacak

## Phase 2 Definition of Done

- [ ] RPC baseline kayıtlı
- [ ] Async analyzer testleri PASS
- [ ] Parallel RPC benchmark PASS
- [ ] Scanner async benchmark PASS
- [ ] Paper/Portfolio regression PASS
- [ ] API performance regression PASS
- [ ] Compile PASS
- [ ] Import PASS
- [ ] Full tests PASS
- [ ] Smoke tests PASS
- [ ] Clean venv PASS
- [ ] Dead code audit PASS
- [ ] Git clean
- [ ] Roadmap güncel
- [ ] Final performance audit PASS

Status

🚧 In Progress

---

# PHASE 3 — Strategy

Amaç

Karar kalitesini artırmak.

## Yapılacaklar

- [ ] Honeypot
- [ ] Strategy config
- [ ] Config driven thresholds
- [ ] Pool age filter
- [ ] Exposure limits

Status

⏳ Waiting

---

# PHASE 4 — API

Amaç

Deployment.

## Yapılacaklar

- [ ] FastAPI auth
- [ ] Health endpoint
- [ ] Stats endpoint
- [ ] Dockerfile
- [ ] docker-compose
- [ ] .env.example

Status

⏳ Waiting

---

# PHASE 5 — Metrics

Amaç

Gözlemlenebilirlik.

## Yapılacaklar

- [ ] Metrics
- [ ] Telegram Alerts
- [ ] /metrics
- [ ] Telegram env

Status

⏳ Waiting

---

# PHASE 6 — Live Preparation

Amaç

Paper Trading doğrulandıktan sonra Live Trading hazırlığı.

## Yapılacaklar

- [ ] Swap Engine
- [ ] Execution Guard
- [ ] Trading Mode
- [ ] Private RPC
- [ ] Emergency Stop

Status

⏳ Waiting

---

# PHASE 7 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 8 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 9 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 10 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 11 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 12 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 13 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 14 — Reserved

Amaç

İleride resmi olarak tanımlanacak.

Status

⏳ Waiting

---

# PHASE 15 — Final Roadmap Phase

Amaç

Final fazın kapsamı zamanı geldiğinde resmi olarak tanımlanacak.

Kural

Phase 15 roadmap'in son fazıdır.
Phase 16 oluşturulmaz.

Status

⏳ Waiting

---

# Definition of Done

Bir görev ancak aşağıdakilerin tamamı PASS ise tamamlanmış sayılır.

- Plan
- Code
- Compile
- Import
- Test
- Smoke Test
- Commit
- Push
- Roadmap Update
- Final Audit

---

# Test History

Phase 1

- Compile ✅
- Import ✅
- 36/36 Tests ✅
- Smoke Test ✅
- Pipeline PASS ✅
- Git Clean ✅
