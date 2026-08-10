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

Mevcut pipeline'ı ölçülebilir biçimde hızlandırmak.

Ana prensip

Ölçmeden optimizasyon yapılmaz.
Çalışan karar mantığı performans uğruna değiştirilmez.
Öncelik gerçek RPC / HTTP gecikmesi, gereksiz tekrar çağrılar ve kontrollü paralelliktir.

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

## PHASE 2A — RPC + Cache Baseline

Ölçülen gerçek RPC değerleri

- [x] Token analyzer avg ≈ 343 ms
- [x] Pair analyzer avg ≈ 83 ms
- [x] Risk analyzer avg ≈ 28 ms
- [x] Sequential analyzer chain avg ≈ 461 ms

Doğrulanan mevcut durum

- [x] analyzer çağrıları sequential
- [x] erc20_cache tablosu mevcut
- [x] pair_cache tablosu mevcut
- [x] bytecode_cache tablosu mevcut
- [x] analyzer cache tabloları runtime'da kullanılmıyor
- [x] aynı token tekrar analiz edildiğinde RPC tekrar çağrılıyor
- [x] MAX_RPC_CANDIDATES = 30 koruması mevcut
- [x] 1000 satır filter yaklaşık 1–3 ms seviyesinde
- [ ] cache hit / miss politikası belirle
- [ ] analyzer cache TTL politikası belirle
- [ ] güvenli cache reuse tasarımını tamamla
- [ ] performans hedeflerini kilitle

Kural

Phase 2B başlamadan önce hangi verinin ne kadar süre cache'lenebileceği açıkça belirlenir.

---

## PHASE 2B — Analyzer Cache Reuse

- [ ] ERC20 metadata cache read
- [ ] ERC20 metadata cache write
- [ ] Pair result cache read
- [ ] Pair result cache write
- [ ] Bytecode risk cache read
- [ ] Bytecode risk cache write
- [ ] cache TTL
- [ ] stale cache davranışı
- [ ] RPC failure durumunda güvenli fallback
- [ ] cache hit / miss metriği
- [ ] tekrar analiz benchmark
- [ ] full regression tests

Kural

Cache eski veya eksik veriyi güvenli veri gibi gösteremez.
UNKNOWN fail-safe davranışı korunur.

---

## PHASE 2C — Async Analyzer Contracts

- [ ] analyzer/token async
- [ ] analyzer/pair async
- [ ] risk/bytecode async
- [ ] mevcut sync davranışını koru
- [ ] success / error / data sözleşmesini koru
- [ ] analyzer timeout politikası
- [ ] analyzer exception isolation
- [ ] sync vs async regression tests

Kural

Async dönüşüm karar veya risk anlamını değiştiremez.

---

## PHASE 2D — Bounded Parallel RPC

- [ ] Token / Pair / Risk bağımsız çağrılarını paralel çalıştır
- [ ] bounded concurrency
- [ ] tek analyzer hatası diğer analyzer'ları düşürmesin
- [ ] tek token hatası diğer tokenları durdurmasın
- [ ] RPC rate-limit koruması
- [ ] timeout guard
- [ ] sequential vs parallel benchmark
- [ ] provider call amplification kontrolü

Kural

Sınırsız concurrency yok.
1000 token = 1000 eşzamanlı RPC değildir.

---

## PHASE 2E — Burst / Load Validation

Amaç

Yoğun token girişinde mevcut aday filtresi ve RPC bütçesinin davranışını doğrulamak.

- [ ] 1k candidate synthetic burst
- [ ] 5k candidate synthetic burst
- [ ] 10k candidate synthetic burst
- [ ] filter latency p50 / p95 / p99
- [ ] candidate count before filter
- [ ] candidate count after filter
- [ ] RPC admission count
- [ ] duplicate candidate davranışı
- [ ] repeated-cycle davranışı
- [ ] CPU ölçümü
- [ ] RAM ölçümü
- [ ] total cycle latency
- [ ] RPC call count
- [ ] rate-limit davranışı
- [ ] fırsat kaçırma riskini değerlendir

Kural

Load test önce sentetik / kontrollü yapılır.
Gerçek dış servisleri binlerce çağrı ile zorlamak yasaktır.

---

## PHASE 2F — Scanner HTTP Performance

- [ ] GeckoTerminal HTTP latency baseline
- [ ] mevcut requests davranışını ölç
- [ ] aiohttp gerekliliğini kanıtla
- [ ] async HTTP yalnız ölçüm fayda gösterirse uygula
- [ ] HTTP timeout
- [ ] 429 rate-limit davranışı
- [ ] bounded retry / backoff
- [ ] scanner unit testleri offline kalacak
- [ ] live smoke ayrı tutulacak

Kural

Canlı API unit test suite içine alınmaz.

---

## PHASE 2G — Paper / Portfolio Performance

- [ ] paper manager DB query audit
- [ ] paper position processing benchmark
- [ ] gereksiz sorguları kaldır
- [ ] PortfolioService gerekliliğini doğrula
- [ ] Manager refactor yalnız ihtiyaç varsa
- [ ] WAL / singleton davranışını koru
- [ ] paper regression tests

Kural

Paper doğruluğu performans uğruna değiştirilemez.

---

## PHASE 2H — API Performance Scope Check

- [ ] mevcut API runtime kullanımını doğrula
- [ ] API refactor gerçekten gerekli mi belirle
- [ ] gereksiz dependency ekleme
- [ ] Phase 4 deployment işlerini Phase 2'ye çekme

Kural

Phase 2 yalnız performans işidir.
Auth / deployment / production API Phase 4 kapsamındadır.

---

## Performans Güvenlik Sınırları

- [ ] Live trading yok
- [ ] Wallet signing yok
- [ ] Private key kullanımı yok
- [ ] Strategy threshold değişikliği yok
- [ ] Risk skor mantığı değişikliği yok
- [ ] UNKNOWN fail-safe korunacak
- [ ] MAX_RPC_CANDIDATES korunacak veya yalnız benchmark kanıtıyla değişecek
- [ ] External rate-limit dikkate alınacak
- [ ] Her kod değişikliğinden sonra full test çalışacak

## Phase 2 Definition of Done

- [ ] Cache reuse regression PASS
- [ ] Async analyzer regression PASS
- [ ] Parallel RPC benchmark PASS
- [ ] 1k / 5k / 10k synthetic burst PASS
- [ ] Scanner performance regression PASS
- [ ] Paper/Portfolio regression PASS
- [ ] Compile PASS
- [ ] Import PASS
- [ ] Full tests PASS
- [ ] Smoke tests PASS
- [ ] Clean venv PASS
- [ ] Dead code audit PASS
- [ ] Git clean
- [ ] TEST_RESULTS.md güncel
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
