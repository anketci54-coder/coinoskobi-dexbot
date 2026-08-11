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

Current Phase : PHASE 5 — CLOSED
Next Phase : PHASE 6

Progress

- Phase 0 : ✅
- Phase 1 : ✅
- Phase 2 : ✅
- Phase 3 : ✅
- Phase 4 : ✅
- Phase 5 : ✅
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

- [x] chain
- [x] chain_id
- [x] dex
- [x] pool
- [x] token
- [x] quote_token
- [x] source
- [x] liquidity
- [x] volume_24h
- [x] buys_24h
- [x] fdv
- [x] price_usd
- [x] created_at
- [x] observed_at

Identity kuralları

- [x] token identity = chain + token
- [x] pool identity = chain + dex + pool
- [x] duplicate collapse chain-aware olacak
- [x] analyzer cache key chain-aware olacak
- [x] aynı address farklı chain'de duplicate sayılmayacak

Kural

İkinci network eklenmeden önce identity chain-aware hale getirilir.

---

## PHASE 2F — Network / DEX Adapter Registry

Amaç

Yeni network veya DEX eklemeyi çekirdek pipeline değişikliği olmaktan çıkarmak.

Başlangıç aktif scope

- [x] BSC adapter
- [x] PancakeSwap source mapping
- [x] GeckoTerminal BSC source adapter

Registry modeli

- [x] network registry
- [x] DEX registry
- [x] enabled / disabled flag
- [x] chain_id
- [x] source adapter
- [x] supported DEX mapping
- [x] provider/RPC config binding

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

- [x] sabit token batch mantığını çekirdek akıştan kaldır
- [x] worker boşaldığında sıradaki uygun işi al
- [x] WARM hızlı hat
- [x] PARTIAL yalnız eksik analyzer
- [x] COLD pahalı worker hattı
- [x] bounded analyzer concurrency
- [x] provider timeout
- [x] provider rate-limit koruması
- [x] exception isolation
- [x] backlog metriği
- [~] queue age metriği — final Faz 2 kapasite testinde zorunlu görülmedi; ihtiyaç oluşursa sonraki performans çalışmasına bırakıldı
- [~] worker utilization metriği — bounded concurrency ve capacity testleri yeterli bulundu; kalıcı telemetry eklenmedi

Kural

Sınır token sayısında değildir.

Sınır gerçek eşzamanlı pahalı iş kapasitesindedir.

---

## PHASE 2H — Multi-Network Fairness

Amaç

Bir network yoğunlaştığında diğer networklerin starvation yaşamamasını sağlamak.

İlk sürüm basit tutulur.

- [x] chain-aware scheduling
- [x] basit round-robin veya eşdeğer fairness
- [x] tek chain bütün worker havuzunu sürekli işgal edemez
- [x] unused capacity boş bırakılmaz
- [x] aktif tek network varken tüm uygun kapasiteyi kullanabilir
- [x] ikinci mock network ile regression test

Kural

15 ayrı pipeline veya gereksiz karmaşık scheduler yapılmaz.

---

## PHASE 2I — Scanner / HTTP Performance

- [x] GeckoTerminal HTTP latency baseline güncelle
- [x] requests yeterli mi ölç
- [x] async HTTP gerçekten fayda sağlıyor mu kanıtla
- [~] gerekirse aiohttp — ölçüm sonucu gerekli olmadığı için eklenmedi
- [x] HTTP timeout
- [x] 429 handling
- [x] bounded retry / backoff
- [x] unit testler offline kalacak
- [x] live smoke ayrı kalacak

Kural

Ölçüm fayda göstermiyorsa HTTP katmanı yeniden yazılmaz.

---

## PHASE 2J — Paper / Portfolio Performance

- [x] paper manager DB query audit
- [x] position processing benchmark
- [x] gereksiz query varsa kaldır — kaldırılması gereken bariz query bulunmadı
- [x] PortfolioService gerekliliği değerlendirildi — yeni servis gerekmedi
- [x] Manager refactor ihtiyacı değerlendirildi — refactor gerekmedi
- [x] WAL / singleton davranışını koru
- [x] paper regression PASS

---

## PHASE 2K — Final Scale Validation

Test matrisleri

- [x] 1k unique candidate
- [x] 15k unique candidate
- [x] 100k unique candidate
- [x] mixed WARM / PARTIAL / COLD
- [x] duplicate storm
- [x] cold-cache startup
- [x] warm-cache steady state
- [x] provider slowdown
- [x] provider error
- [x] second-network mock
- [x] multi-network fairness
- [x] cache hit rate
- [~] queue age — permanent runtime telemetry intentionally deferred
- [x] backlog
- [~] worker utilization — permanent runtime telemetry intentionally deferred
- [x] CPU
- [x] RAM
- [x] p50 / p95 / p99 latency — HTTP/analyzer baselines measured during Faz 2
- [x] valuable-candidate preservation

Gerçek dış providerlara load test sırasında binlerce gereksiz RPC gönderilmez.

---

## Phase 2 Definition of Done

- [x] Common Candidate Model PASS
- [x] chain-aware identity PASS
- [x] source adapter registry PASS
- [x] network registry PASS
- [x] DEX registry PASS
- [x] conveyor routing PASS
- [x] worker scheduler PASS
- [x] multi-network fairness PASS
- [x] analyzer cache regression PASS
- [x] scanner regression PASS
- [x] paper regression PASS
- [x] 1k / 15k / 100k scale validation PASS
- [x] second-network mock PASS
- [x] Compile PASS
- [x] Import PASS
- [x] Full tests PASS
- [x] Smoke PASS
- [x] Clean venv PASS
- [x] DB integrity PASS
- [x] Dead code audit PASS
- [x] TEST_RESULTS.md güncel
- [x] Roadmap güncel
- [x] Git clean
- [x] Final performance audit PASS

Status

✅ Completed

---


## Phase 2 Final Closure — 2026-08-10

Final doğrulama:

- 1K mixed candidate: 1000 / 1000 processed, 0 failed, 0 pending
- 15K mixed candidate: 15000 / 15000 processed, 0 failed, 0 pending
- 100K mixed candidate: 100000 / 100000 processed, 0 failed, 0 pending
- 100K throughput: ≈ 6,440 candidate/sec
- 100K peak Python allocation: ≈ 142.6 MB
- Mixed lanes: %70 WARM / %20 PARTIAL / %10 COLD
- Multi-network: BSC + mock second-network PASS
- Duplicate storm: 10,000 events → 100 unique, 9,900 duplicate collapsed
- Chain-aware same-address isolation PASS
- Legacy MAX_RPC_CANDIDATES / pop_many architecture absent
- Paper manager process ≈ 0.82 ms
- cache.db integrity / quick_check PASS, WAL
- paper_trades.db integrity / quick_check PASS, WAL
- Targeted Phase 2 regression: 68 passed
- Full regression: 128 passed / 0 failed
- Compile PASS
- Import smoke PASS
- GeckoTerminal live smoke: 20 raw / 20 normalized / 0 rejected
- Dead script / smoke / E2E inventory PASS
- 25 / 25 test files actively collected
- Generated cache/temp cleanup PASS
- Git working tree clean before closure documentation

Known non-blocking warning:

- `websockets.legacy` deprecation warning from dependency stack.

Architecture outcome:

RAW
→ Source/Network Registry
→ Adapter
→ Common Candidate
→ Ingress Gate
→ Conveyor WARM/PARTIAL/COLD
→ Chain-aware Priority Queue
→ Cost-aware + Multi-network Fair Work Scheduler
→ Analyzer Cache / RPC
→ Strategy

Faz 2 sonucu:

**PHASE 2: ✅ CLOSED**

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

# LEGACY PHASE 4 — API (SUPERSEDED)

> Historical roadmap section only.
> Phase numbering was superseded by the canonical Phase 4-6 architecture
> defined later in this document. Do not use this section as the active roadmap.


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

# LEGACY PHASE 5 — Metrics (SUPERSEDED)

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

# LEGACY PHASE 6 — Live Preparation (SUPERSEDED)

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

---

## Phase 3 Final Closure — 2026-08-11

Phase 3 scope:

**Risk + Opportunity + Entry Feasibility**

Completed architecture:

- Strategy thresholds moved to config
- Honeypot / sellability hard-block contract
- Bounded sellability deep-check
- Trap / tax / transfer-control signals
- MEV / sandwich exposure model
- Market context binding
- Unified risk / opportunity score
- Score confidence / evidence coverage
- Unified advisory decision contract
- Execution-cost / entry-feasibility model
- Unknown evidence does not become automatic risk
- Hard-block remains separate from mathematical score
- No live / wallet / execution authority added

Final validation:

- Phase 3 targeted regression: 83 passed / 0 failed
- Full repository regression: 198 passed / 0 failed
- Compile PASS
- Config duplicate audit PASS
- No live/wallet transaction surface detected
- Unified score pure-local
- Unified decision pure-local
- Execution-cost engine pure-local
- Worktree clean before closure documentation

Authority boundaries:

- Confirmed honeypot / unsellable can hard-block
- Suspicion / UNKNOWN does not hard-block
- Trap signals do not own trade authority
- MEV exposure does not own trade authority
- Unified score does not own trade authority
- Unified decision remains advisory
- Execution-cost model remains advisory
- Existing paper path remains separate
- Live execution remains outside Phase 3

Phase boundary:

**Phase 3 answers: "Bu adaya girmek mantıklı mı?"**

Deferred to Phase 4:

- Multi-stage TP
- Runner position
- Trend-following / adaptive SL
- DEX-native swap-flow momentum
- Volume quality
- Unique buyer/seller participation
- Liquidity/reserve trend dynamics
- Momentum exhaustion / divergence
- Runner exit intelligence
- Position lifecycle management

Final result:

**PHASE 3: ✅ CLOSED**

Next:

**PHASE 4 — Position Lifecycle / DEX Exit Intelligence**

---

---

# Phase 4 — Position Lifecycle

Status: PLANNED

Primary question:

**"Pozisyona girdikten sonra mekanik olarak nasıl yöneteceğiz?"**

Scope:

## 4A — Position Lifecycle Baseline Audit
- Existing paper position schema
- Entry / current / highest / lowest price
- Existing TP / SL behavior
- Existing close path
- Position persistence
- Phase 0-3 integration boundary

## 4B — Multi-TP Contract
- Config-driven TP allocation
- Partial position reduction
- TP1 / TP2
- Remaining runner allocation
- No DEX trend intelligence yet

## 4C — Position State Machine
Target lifecycle:

OPEN
→ TP1_HIT
→ TP2_HIT
→ RUNNER_ACTIVE
→ CLOSED

Additional terminal/protective states:
- STOPPED
- HARD_RISK_EXIT
- INVALID_POSITION

State transitions must be deterministic and testable.

## 4D — Protective / Monotonic Trailing SL
- Initial protective SL
- SL may tighten upward
- SL must never loosen downward for long positions
- Explicit transition/evidence
- No indicator-based intelligence yet

Core invariant:

**new_stop >= previous_stop**

## 4E — Runner Mechanics
- Runner has no mandatory fixed final TP
- Runner keeps remaining position open
- Runner accepts future exit/trailing intelligence
- Runner mechanics remain separate from intelligence source
- No live execution authority

## 4F — Phase 4 Validation / Closure
- Paper lifecycle simulation
- Partial-close regression
- State-transition tests
- Gap / price-jump scenarios
- E2E Phase 0-4
- Speed test
- Full regression
- Authority audit
- Final freeze

Phase boundary:

**Phase 4 builds the position-management machine.**

It does NOT decide whether DEX momentum is healthy.

---

# Phase 5 — DEX Market Intelligence

Status: PLANNED

Primary question:

**"DEX piyasasında şu anda gerçekte ne oluyor?"**

Design principle:

DEX-native evidence first.

Do not copy a CEX indicator stack blindly.

## 5A — DEX Data / Signal Baseline
- Available swap/pool data inventory
- Data freshness
- Source lineage
- Cache strategy
- Missing-data semantics
- Cost / provider boundaries

## 5B — Swap Flow / Momentum
- Buy vs sell swap flow
- Buy/sell notional imbalance
- Swap frequency
- Flow acceleration/deceleration
- Short-window vs longer-window momentum
- Large-swap distortion protection

## 5C — Volume Quality / Participation
- Real volume quality
- Unique buyers
- Unique sellers
- Buyer/seller participation ratio
- Repeat-wallet concentration
- Burst activity
- Suspicious/self-repeating flow indicators

Raw volume alone must NOT imply healthy momentum.

## 5D — Wallet Concentration / Flow Quality
- Concentration of active flow
- Top-wallet contribution
- New-wallet participation
- Repeated-wallet dominance
- Distribution quality

No automatic identity/whale conclusion from address activity alone.

## 5E — Liquidity / Reserve Dynamics
- Liquidity trend
- Reserve changes
- Liquidity additions/removals
- Price movement relative to reserve movement
- Liquidity deterioration
- Sudden pool-depth changes

## 5F — Price Impact / Market Depth Context
- Trade-size / liquidity ratio
- Expected price impact
- Slippage context
- Market depth deterioration
- Existing Phase 3 MEV context reuse
- No duplicate penalty model

## 5G — DEX Market Signal Bundle
Produce a bounded deterministic readmodel such as:

- flow_momentum
- flow_acceleration
- volume_quality
- participation_quality
- wallet_concentration
- liquidity_health
- reserve_trend
- price_impact_health
- freshness
- coverage

Signal bundle has:

- trade_authority = false
- decision_authority = false
- execution_authority = false

## 5H — Phase 5 Validation / Closure
- Synthetic DEX scenarios
- Missing/stale-data scenarios
- Manipulated-volume scenarios
- Liquidity-shock scenarios
- E2E Phase 0-5
- Performance / cache tests
- Full regression
- Authority audit
- Final freeze

Phase boundary:

**Phase 5 observes and describes the DEX market.**

It does NOT directly close the runner.

---

# Phase 6 — DEX Exit Intelligence

Status: PLANNED

Primary question:

**"Trend hâlâ taşıyor mu; runner devam mı etmeli, korunmalı mı, çıkışa mı hazırlanmalı?"**

Input:

Phase 4 position lifecycle
+
Phase 5 DEX market signal bundle
+
existing Phase 3 risk / cost evidence

## 6A — Exit Intelligence Baseline
- Define exit-state inputs
- Position-state binding
- Freshness requirements
- UNKNOWN behavior
- Hard-risk separation

## 6B — DEX Trend Health
Combine DEX-native evidence into deterministic states:

- STRONG
- HEALTHY
- WEAKENING
- BREAK
- UNKNOWN

Inputs may include:
- swap-flow momentum
- flow acceleration
- participation quality
- volume quality
- liquidity/reserve health
- price-impact deterioration

No single indicator owns the exit decision.

## 6C — Momentum Exhaustion
Detect cases where:

price continues upward
BUT
supporting DEX flow weakens.

Examples:
- price higher / buy flow weaker
- price higher / volume quality weaker
- price higher / unique participation falling
- price higher / sell pressure accelerating
- price higher / liquidity deteriorating

This is the core of the previously discussed
"price reaches 175 but momentum dies" problem.

## 6D — Divergence / Exit Pressure
- Flow-price divergence
- Participation-price divergence
- Liquidity-price divergence
- Sell-pressure acceleration
- Exhaustion persistence
- Noise/debounce protection

## 6E — Runner Health Model
Runner state interpretation:

- RUNNER_HEALTHY
- RUNNER_PROTECT
- RUNNER_TIGHTEN
- RUNNER_EXIT_CANDIDATE
- RUNNER_EMERGENCY_EXIT_CONTEXT
- UNKNOWN

Intelligence remains separate from wallet/live execution.

## 6F — Adaptive Trailing-SL Intelligence
Phase 6 recommends how Phase 4 trailing mechanics should behave.

Concept:

Strong trend
→ allow breathing room

Healthy trend
→ normal trailing

Weakening trend
→ tighten protection

Confirmed break
→ exit candidate

For long positions:

**recommended_stop must never reduce an already protected stop.**

## 6G — Risk / Exit Override Context
Reuse existing evidence:
- honeypot/sellability
- tax changes
- MEV exposure
- liquidity collapse
- execution feasibility

Hard safety remains superior to trend score.

High momentum can never override confirmed critical risk.

## 6H — Runner Exit Contract
Final advisory output contains:
- trend_health
- exhaustion_state
- runner_health
- trailing_recommendation
- exit_pressure
- evidence
- confidence
- freshness
- reasons

Authority remains explicit:
- live_authority = false
- wallet_authority = false
- execution_authority = false

## 6I — Paper / Shadow Stress Validation
Scenarios include:
- clean sustained pump
- pump then exhaustion
- fake-volume pump
- whale-driven spike
- liquidity withdrawal during rise
- sharp reversal
- slow trend decay
- noisy sideways market
- price makes new high while DEX momentum weakens

Measure:
- profit retained
- premature exits
- late exits
- maximum giveback
- runner capture
- false exit signals

## 6J — Phase 6 Final Audit / Freeze
- Phase 0-6 E2E
- Stress regression
- Performance
- UNKNOWN/freshness audit
- Risk authority audit
- No live/wallet authority
- Full regression
- Final freeze

Phase boundary:

**Phase 6 turns DEX evidence into exit intelligence.**

It does not grant autonomous live execution authority.

---

# Locked Phase 4-6 Data Flow

Phase 3:
ENTRY RISK / OPPORTUNITY / FEASIBILITY
        ↓
Phase 4:
POSITION LIFECYCLE / TP / SL / RUNNER MECHANICS
        ↓
Phase 5:
DEX MARKET OBSERVATION / FLOW / LIQUIDITY / PARTICIPATION
        ↓
Phase 6:
TREND HEALTH / EXHAUSTION / ADAPTIVE RUNNER EXIT INTELLIGENCE

Core separation:

**Mechanics != Market Evidence != Exit Intelligence**

---

---

## Phase 4 Final Closure — 2026-08-11

Scope:

**Position Lifecycle Mechanical Core**

Completed:

- Multi-TP mechanical contract
- TP1 / TP2 / TP3 staged progression
- Allocation: 20% / 25% / 25% / 30% runner
- Deterministic position state machine
- Duplicate TP protection
- No TP skipping
- Fraction conservation
- Runner activation after TP3
- Protective monotonic trailing stop
- Stop never loosens downward
- Highest price never moves backward
- Gap-up / gap-down handling
- Runner has no mandatory fixed final TP
- Runner protective exit-candidate contract

Final validation:

- Phase 4 targeted: 41 passed / 0 failed
- Phase 0-4 connection regression: 183 passed / 0 failed
- Full regression: 239 passed / 0 failed
- Compile PASS
- DB integrity PASS
- Phase 4 speed: ~51,329 lifecycle ops/sec
- Worktree clean

Authority:

- decision_authority = false
- paper_authority = false
- live_authority = false
- wallet_authority = false
- execution_authority = false

Important boundary:

Phase 4 mechanical core is validated but not yet bound into
PaperManager/runtime execution.

Phase 4 answers:

**"Pozisyonu mekanik olarak nasıl yöneteceğiz?"**

Next:

**PHASE 5 — DEX Market Intelligence**

Phase 5 begins real DEX data observation and processing.

---


---

## Phase 5 Final Closure — 2026-08-11

Scope:

**DEX Market Intelligence / Short-Horizon Observation Core**

Completed:

- Real GeckoTerminal BSC baseline inspection
- Real bounded external DEX read
- PancakeSwap V2 event ABI contracts:
  - PairCreated
  - Swap
  - Sync
  - Mint
  - Burn
- Normalized DEX event contract
- Short-horizon market clock:
  - wall-clock windows: 250ms / 500ms / 1s / 2s / 5s / 10s / 30s
  - block windows: 1 / 2 / 4 / 8 / 16 / 32 blocks
  - swap windows: 5 / 10 / 25 / 50 / 100 swaps
- Swap-flow mechanical analyzer
- Buy/sell count imbalance
- Buy/sell volume imbalance
- Volume quality context
- Unique buyer/seller participation context
- Transaction participation ratio
- Liquidity / reserve deterioration context
- Suspicious concentrated-volume signal
- Pure-local authority boundaries

Real-data validation:

- GeckoTerminal real read: 20 rows
- External read bounded
- Phase 5 targeted: 14 passed / 0 failed
- Phase 0-5 connection regression: 95 passed / 0 failed
- Full regression: 253 passed / 0 failed
- Compile PASS
- Cache DB unchanged
- Paper DB unchanged
- DB integrity PASS
- Worktree clean

Authority:

- decision_authority = false
- paper_authority = false
- live_authority = false
- wallet_authority = false
- execution_authority = false

Important evidence boundary:

The Phase 5E real-data validation used real GeckoTerminal aggregate
market data to validate data compatibility and market-quality logic.

The generated SWAP observations used during that bounded validation were
synthetic observation records derived from aggregate rows.

Therefore:

- real external DEX data compatibility is validated
- short-horizon market-clock mechanics are validated
- swap-flow calculations are validated
- real native BSC Swap/Sync streaming is NOT yet claimed as validated
- no continuous WebSocket subscription was enabled
- no paper/live execution behavior was enabled

Phase 6 may consume this Phase 5 observation core only after native
short-horizon event evidence is explicitly validated.

Final Phase 5 state:

**CLOSED / VERIFIED / NO TRADE AUTHORITY**
