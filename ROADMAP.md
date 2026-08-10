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

# MİMARİ ANAYASA

Bu kurallar fazlardan bağımsızdır ve çekirdek mimariyi korur.

- Sistem basit, ölçülebilir ve modüler tutulur.
- Ölçülmemiş performans problemi için karmaşık çözüm eklenmez.
- Network veya DEX için ayrı pipeline kopyalanmaz.
- Bütün kaynaklar ortak bir Candidate sözleşmesine normalize edilir.
- Network ve DEX farklılıkları adapter / registry katmanında kalır.
- Candidate kimliği chain-aware olmak zorundadır.
- Aynı adres farklı ağlarda aynı varlık kabul edilmez.
- Token sayısına göre sabit admission/batch kotası çekirdek mimari prensibi değildir.
- Kapasite worker concurrency, provider kapasitesi, CPU/RAM ve backpressure ile yönetilir.
- Discovery / ingress hattı pahalı RPC veya AI beklemez.
- Ucuz işler ray üzerinde yapılır; pahalı işler worker'lara bırakılır.
- Cache hit olan veri gereksiz yere yeniden RPC'den alınmaz.
- PARTIAL adayda yalnız eksik analiz tamamlanır.
- COLD aday pahalı hatta gider; WARM aday pahalı işi tekrar etmez.
- Duplicate olaylar mümkün olduğunca erken collapse edilir.
- Bir ağdaki yoğunluk gelecekte diğer ağları tamamen aç bırakamaz.
- Yeni network eklemek pipeline rewrite değil adapter/config işi olmalıdır.
- Yeni DEX eklemek strategy veya analyzer kopyalamayı gerektirmemelidir.
- Gereksiz Kafka, Celery, Redis, mikroservis veya dağıtık sistem bağımlılığı eklenmez.
- Mevcut tek-process yapı kapasiteyi karşılıyorsa korunur.
- Optimizasyon karar/risk anlamını değiştiremez.
- UNKNOWN fail-safe davranışı korunur.
- Her kod değişikliğinden sonra regression test çalışır.

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

# PHASE 2 — Performance & Scalable Pipeline Core

Amaç

Coinoskobi'nin token akışını hızlı, sade ve ölçeklenebilir hale getirmek.

Başlangıçta yalnız BSC + PancakeSwap / GeckoTerminal aktif olacaktır.

Çekirdek altyapı ise gelecekte yaklaşık 15 network ve network başına
5-6 DEX eklenebilecek şekilde ortak pipeline mantığıyla tasarlanacaktır.

Ana prensip

Amerika yeniden keşfedilmez.

Standart producer → normalize → filter → queue → worker yaklaşımı kullanılır.

Network ve DEX kaynak katmanıdır.
Pipeline ortak kalır.

Sistem token sayısına göre yapay batch sınırıyla değil,
gerçek işlem kapasitesiyle çalışır.

---

## PHASE 2A — Performance Baseline

Tamamlanan ölçümler

- [x] Compile PASS
- [x] Import smoke PASS
- [x] Full regression baseline PASS
- [x] Clean venv baseline PASS
- [x] DB integrity / quick check PASS
- [x] Scanner unit testi dış ağdan ayrıldı
- [x] GeckoTerminal live smoke PASS
- [x] Cache → Filter baseline ölçüldü
- [x] Filter micro benchmark ölçüldü
- [x] Strategy micro benchmark ölçüldü
- [x] Synthetic Pipeline E2E ölçüldü
- [x] Cycle isolation doğrulandı
- [x] 1k candidate burst ölçüldü
- [x] 15k candidate burst ölçüldü
- [x] 100k candidate burst ölçüldü
- [x] gerçek Token RPC latency ölçüldü
- [x] gerçek Pair RPC latency ölçüldü
- [x] gerçek Risk RPC latency ölçüldü
- [x] combined cold analyzer latency ölçüldü

Doğrulanan darboğaz

CPU tarafındaki ingress/filter hızlıdır.

Ana maliyet cold RPC / external IO tarafındadır.

---

## PHASE 2B — Ingress Gate + Admission Queue

Amaç

Ham adayların pahalı analiz hattına kontrolsüz girmesini önlemek.

- [x] lightweight Ingress Gate
- [x] DROP lane
- [x] DEFER lane
- [x] ACTIVE lane
- [x] bounded pending queue
- [x] duplicate collapse
- [x] cooldown
- [x] priority ordering
- [x] yüksek değerli sentinel preservation testi
- [x] 1k burst queue testi
- [x] 15k burst queue testi
- [x] 100k burst queue testi

Kural

DROP = bu cycle pahalı işlem bütçesi harcanmaz.

DEFER = aday unutulmaz; sonraki cycle tekrar değerlendirilebilir.

ACTIVE = ray üzerinde ilerlemeye hak kazanır.

---

## PHASE 2C — Analyzer Cache Reuse

Amaç

Aynı veriyi tekrar tekrar RPC'den istememek.

- [x] ortak AnalyzerCache
- [x] SQLite WAL
- [x] cache hit / miss
- [x] stale detection
- [x] Token Analyzer cache reuse
- [x] Pair Analyzer cache reuse
- [x] Risk Analyzer cache reuse
- [x] RPC failure sonucu güvenilir cache olarak yazılmıyor
- [x] test cache isolation
- [x] gerçek Token cold / warm benchmark
- [x] gerçek Pair cold / warm benchmark
- [x] gerçek Risk cold / warm benchmark
- [x] combined cold / warm benchmark
- [x] combined warm path sub-millisecond doğrulandı

Ölçülen combined baseline

- Cold analyzer chain ≈ 537 ms
- Warm analyzer chain ≈ 0.17 ms

Kural

Cache hızlandırma katmanıdır.
Risk veya strategy authority değildir.

---

## PHASE 2D — Conveyor / Ray Üstü Etiketleme

Amaç

Tokenı baştan sona tek blokta işlemek yerine,
ray üzerinde ucuz state etiketleriyle yönlendirmek.

- [x] ConveyorLabeler
- [x] WARM etiketi
- [x] PARTIAL etiketi
- [x] COLD etiketi
- [x] token cache state
- [x] pair cache state
- [x] risk cache state
- [x] missing analyzer listesi
- [x] gerçek Gecko live conveyor testi
- [x] cold → warm state transition doğrulaması
- [x] real-shape duplicate replay testi

Hedef akış

RAW
→ Ingress Gate
→ ACTIVE
→ Conveyor
→ WARM / PARTIAL / COLD
→ Worker
→ Strategy

Kural

Ray üstündeki etiketleme ucuz olmalıdır.

Etiketleme RPC, AI veya strategy çalıştırmaz.

---

## PHASE 2E — Common Candidate Model

Amaç

Pipeline'ın BSC veya belirli bir DEX veri formatına bağımlılığını kaldırmak.

Ortak Candidate minimum alanları

- [ ] chain
- [ ] chain_id
- [ ] dex
- [ ] pool
- [ ] token
- [ ] quote_token
- [ ] source
- [ ] liquidity
- [ ] volume_24h
- [ ] buys_24h
- [ ] fdv
- [ ] price_usd
- [ ] created_at
- [ ] observed_at

Identity kuralları

- [ ] token identity = chain + token
- [ ] pool identity = chain + dex + pool
- [ ] duplicate collapse chain-aware olacak
- [ ] analyzer cache key chain-aware olacak
- [ ] aynı address farklı chain'de duplicate sayılmayacak

Kural

İkinci network eklenmeden önce identity chain-aware hale getirilir.

---

## PHASE 2F — Network / DEX Adapter Registry

Amaç

Yeni network veya DEX eklemeyi çekirdek pipeline değişikliği olmaktan çıkarmak.

Başlangıç aktif scope

- [ ] BSC adapter
- [ ] PancakeSwap source mapping
- [ ] GeckoTerminal BSC source adapter

Registry modeli

- [ ] network registry
- [ ] DEX registry
- [ ] enabled / disabled flag
- [ ] chain_id
- [ ] source adapter
- [ ] supported DEX mapping
- [ ] provider/RPC config binding

Kural

Network-specific kod ortak pipeline içine gömülmez.

DEX-specific veri adapter içinde normalize edilir.

---

## Gelecekte Yeni Network Nasıl Eklenir

Yeni network eklemek için standart sıra:

1. Network registry'ye network ekle.
2. chain_id tanımla.
3. RPC/provider config tanımla.
4. Source adapter oluştur veya mevcut generic adapterı kullan.
5. DEX mappinglerini registry'ye ekle.
6. Kaynak verisini ortak Candidate modeline normalize et.
7. Chain-aware identity testlerini çalıştır.
8. Ingress Gate regression çalıştır.
9. Conveyor regression çalıştır.
10. Analyzer/cache regression çalıştır.
11. Multi-network fairness/load test çalıştır.
12. Network disabled durumda davranışı doğrula.
13. Network yalnız testler PASS ise enabled yapılır.

Yeni network için yeni PipelineEngine kopyalanmaz.

Yeni network için strategy kopyalanmaz.

Yeni network için analyzer kopyalanmaz;
yalnız chain davranışı gerçekten farklıysa adapter/implementation ayrılır.

---

## Gelecekte Yeni DEX Nasıl Eklenir

Yeni DEX eklemek için standart sıra:

1. DEX registry'ye DEX ID ekle.
2. Desteklediği networkleri tanımla.
3. Pool/token alanlarını ortak Candidate formatına map et.
4. DEX-specific source parsing adapter içinde kalır.
5. Ortak Ingress Gate kullanılır.
6. Ortak Conveyor kullanılır.
7. Ortak queue/scheduler kullanılır.
8. Ortak strategy kullanılır.
9. DEX-specific istisna ancak teknik zorunluluk varsa eklenir.
10. Regression + live smoke sonrası enabled yapılır.

Kural

Her DEX için ayrı bot veya ayrı pipeline oluşturulmaz.

---

## PHASE 2G — Work Scheduler

Amaç

Ray üzerindeki işleri sistem kapasitesine göre sürekli işlemek.

- [ ] sabit token batch mantığını çekirdek akıştan kaldır
- [ ] worker boşaldığında sıradaki uygun işi al
- [ ] WARM hızlı hat
- [ ] PARTIAL yalnız eksik analyzer
- [ ] COLD pahalı worker hattı
- [ ] bounded analyzer concurrency
- [ ] provider timeout
- [ ] provider rate-limit koruması
- [ ] exception isolation
- [ ] backlog metriği
- [ ] queue age metriği
- [ ] worker utilization metriği

Kural

Sınır token sayısında değildir.

Sınır gerçek eşzamanlı pahalı iş kapasitesindedir.

---

## PHASE 2H — Multi-Network Fairness

Amaç

Bir network yoğunlaştığında diğer networklerin starvation yaşamamasını sağlamak.

İlk sürüm basit tutulur.

- [ ] chain-aware scheduling
- [ ] basit round-robin veya eşdeğer fairness
- [ ] tek chain bütün worker havuzunu sürekli işgal edemez
- [ ] unused capacity boş bırakılmaz
- [ ] aktif tek network varken tüm uygun kapasiteyi kullanabilir
- [ ] ikinci mock network ile regression test

Kural

15 ayrı pipeline veya gereksiz karmaşık scheduler yapılmaz.

---

## PHASE 2I — Scanner / HTTP Performance

- [ ] GeckoTerminal HTTP latency baseline güncelle
- [ ] requests yeterli mi ölç
- [ ] async HTTP gerçekten fayda sağlıyor mu kanıtla
- [ ] gerekirse aiohttp
- [ ] HTTP timeout
- [ ] 429 handling
- [ ] bounded retry / backoff
- [ ] unit testler offline kalacak
- [ ] live smoke ayrı kalacak

Kural

Ölçüm fayda göstermiyorsa HTTP katmanı yeniden yazılmaz.

---

## PHASE 2J — Paper / Portfolio Performance

- [ ] paper manager DB query audit
- [ ] position processing benchmark
- [ ] gereksiz query varsa kaldır
- [ ] PortfolioService gerçekten gerekliyse oluştur
- [ ] Manager refactor yalnız kanıtlanmış ihtiyaç varsa
- [ ] WAL / singleton davranışını koru
- [ ] paper regression PASS

---

## PHASE 2K — Final Scale Validation

Test matrisleri

- [ ] 1k unique candidate
- [ ] 15k unique candidate
- [ ] 100k unique candidate
- [ ] mixed WARM / PARTIAL / COLD
- [ ] duplicate storm
- [ ] cold-cache startup
- [ ] warm-cache steady state
- [ ] provider slowdown
- [ ] provider error
- [ ] second-network mock
- [ ] multi-network fairness
- [ ] cache hit rate
- [ ] queue age
- [ ] backlog
- [ ] worker utilization
- [ ] CPU
- [ ] RAM
- [ ] p50 / p95 / p99 latency
- [ ] valuable-candidate preservation

Gerçek dış providerlara load test sırasında binlerce gereksiz RPC gönderilmez.

---

## Phase 2 Definition of Done

- [ ] Common Candidate Model PASS
- [ ] chain-aware identity PASS
- [ ] source adapter registry PASS
- [ ] network registry PASS
- [ ] DEX registry PASS
- [ ] conveyor routing PASS
- [ ] worker scheduler PASS
- [ ] multi-network fairness PASS
- [ ] analyzer cache regression PASS
- [ ] scanner regression PASS
- [ ] paper regression PASS
- [ ] 1k / 15k / 100k scale validation PASS
- [ ] second-network mock PASS
- [ ] Compile PASS
- [ ] Import PASS
- [ ] Full tests PASS
- [ ] Smoke PASS
- [ ] Clean venv PASS
- [ ] DB integrity PASS
- [ ] Dead code audit PASS
- [ ] TEST_RESULTS.md güncel
- [ ] Roadmap güncel
- [ ] Git clean
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
