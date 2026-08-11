# COINOSKOBI DEXBOT — ROADMAP

Bu dosya Coinoskobi'nin resmi ve kronolojik geliştirme planıdır.

Temel kural:

**Her şey kendi yerine gider; gerekli olmayan hiçbir şey değişmez.**

Fazlar yukarıdan aşağıya ilerler.

Bir faz kapanırken:
- gerçekleşen kapsam kendi fazına yazılır
- gerçekten alınmış kalıcı kararlar kendi fazına yazılır
- kısa doğrulama sonucu kendi fazına yazılır
- eksikler ve sonraya bırakılan işler kendi fazına yazılır
- fazın gerçek durumu güncellenir
- aynı anda yalnızca bir sonraki fazın başlangıç planı hazırlanır

Tam terminal çıktıları, geçici probe kayıtları ve disposable audit scriptleri
ROADMAP içinde tutulmaz.

---

# PROJE DURUMU

Current Phase: **PHASE 8 — CLOSED**

Next Phase: **PHASE 9 — RESERVED**

Progress:

- Phase 0: ✅ CLOSED
- Phase 1: ✅ CLOSED
- Phase 2: ✅ CLOSED
- Phase 3: ✅ CLOSED
- Phase 4: ✅ CLOSED
- Phase 5: ✅ CLOSED
- Phase 6: ✅ CLOSED
- Phase 7: ✅ CLOSED
- Phase 8: ✅ CLOSED
- Phase 9: ⏳ WAITING
- Phase 10: ⏳ WAITING
- Phase 11: ⏳ WAITING
- Phase 12: ⏳ WAITING
- Phase 13: ⏳ WAITING
- Phase 14: ⏳ WAITING
- Phase 15: ⏳ WAITING

---

# MİMARİ ANAYASA

Bu kararlar fazlardan bağımsızdır.

- Sistem modüler, ölçülebilir ve sade tutulur.
- BSC başlangıç ağıdır.
- Network veya DEX için ayrı pipeline kopyalanmaz.
- Kaynaklar ortak Candidate sözleşmesine normalize edilir.
- Candidate identity chain-aware olmak zorundadır.
- Discovery / ingress hattı pahalı RPC veya AI beklemez.
- Ucuz işler hızlı hatta yapılır.
- Pahalı işler bounded worker hattına bırakılır.
- Cache hit olan veri gereksiz yere yeniden alınmaz.
- PARTIAL adayda yalnız eksik analiz tamamlanır.
- WARM aday pahalı işi tekrar etmez.
- COLD aday gerekli pahalı analize gider.
- Duplicate olaylar mümkün olduğunca erken collapse edilir.
- Provider failure güvenli veri gibi yorumlanmaz.
- UNKNOWN gerektiğinde UNKNOWN kalır.
- Hard safety gate matematiksel skordan üstündür.
- Observation authority, decision authority ve execution authority ayrıdır.
- Market intelligence wallet imzalama yetkisi taşımaz.
- Live execution ayrı ve açık bir faz gerektirir.
- Private key, seed phrase ve secret repository'ye yazılmaz.
- Gereksiz Kafka, Celery, Redis veya mikroservis eklenmez.
- Performans ölçülmeden karmaşıklık eklenmez.
- Her faz kapanmadan targeted, smoke, E2E ve regression doğrulaması yapılır.

---

# PHASE 0 — Critical Bug Fixes

## Amaç

Botun temel olarak çalışır ve test edilebilir hale gelmesi.

## Sisteme Eklenenler

- Gecko pool cache `price_usd` desteği
- CachePrice uyumluluğu
- ALLOWED_DEX filtresi
- requirements temizliği
- gereksiz scanner pair dosyasının kaldırılması
- duplicate portfolio yapısının kaldırılması

## Alınan Kararlar

- Çekirdek davranış sade tutulacak.
- Aynı işi yapan duplicate modüller bırakılmayacak.
- Geçici scriptler kalıcı mimarinin parçası olmayacak.

## Faz Sonu Sistem Durumu

Temel scanner/cache/paper altyapısı çalışabilir hale getirildi.

## Status

✅ CLOSED

---

# PHASE 1 — Core Infrastructure

## Amaç

Temiz, sürdürülebilir ve test edilebilir temel altyapıyı kurmak.

## Sisteme Eklenenler

- core logger
- core runner
- paper database
- SQLite WAL
- database singleton
- trading config
- contract config
- sadeleştirilmiş main entry
- gereksiz factory/router/token katmanlarının kaldırılması

## Alınan Kararlar

- SQLite mevcut kapasiteyi karşıladığı sürece korunacak.
- Yapay dağıtık mimari eklenmeyecek.
- Config ve runtime sorumlulukları ayrılacak.

## Faz Sonu Sistem Durumu

Coinoskobi temiz bir çekirdek uygulama yapısına sahip oldu.

## Status

✅ CLOSED

---

# PHASE 2 — Performance & Scalable Pipeline Core

## Amaç

Token akışını hızlı, bounded ve gelecekte çoklu network/DEX desteğine uygun hale getirmek.

## Sisteme Eklenenler

### Performance Baseline

- compile/import baseline
- full regression baseline
- DB integrity baseline
- GeckoTerminal live smoke
- 1K / 15K / 100K candidate burst ölçümleri
- gerçek RPC latency ölçümleri
- cold / warm analyzer ölçümleri

### Ingress ve Admission

- lightweight ingress gate
- ACTIVE / DEFER / DROP lanes
- bounded candidate queue
- duplicate collapse
- cooldown
- priority ordering

### Analyzer Cache

- ortak AnalyzerCache
- SQLite WAL
- cache hit / miss
- stale detection
- token/pair/risk cache reuse
- RPC failure'ın güvenilir cache olarak yazılmaması

### Conveyor

- WARM
- PARTIAL
- COLD
- eksik analyzer listesi
- cold → warm transition

### Common Candidate Model

- chain
- chain_id
- dex
- pool
- token
- quote_token
- source
- liquidity
- volume_24h
- buys_24h
- fdv
- price_usd
- created_at
- observed_at

### Registry / Adapter

- network registry
- DEX registry
- source adapter registry
- BSC adapter
- GeckoTerminal BSC adapter
- PancakeSwap mapping

### Scheduler

- bounded worker scheduler
- WARM/PARTIAL/COLD scheduling
- chain-aware fairness
- multi-network round-robin
- provider timeout / failure isolation

## Alınan Kararlar

- Network eklemek pipeline rewrite değildir.
- DEX eklemek strategy kopyalamak değildir.
- Token identity = chain + token.
- Pool identity = chain + dex + pool.
- Worker kapasitesi token sayısıyla değil gerçek pahalı iş kapasitesiyle sınırlanır.
- Fast path RPC/AI beklemez.
- Cache hızlandırma katmanıdır; risk authority değildir.

## Doğrulama

- 1K candidate PASS
- 15K candidate PASS
- 100K candidate PASS
- multi-network fairness PASS
- duplicate storm PASS
- chain-aware identity PASS
- warm cache sub-millisecond seviyesinde doğrulandı
- targeted regression PASS
- full regression PASS
- smoke PASS
- DB integrity PASS

## Faz Sonu Sistem Durumu

Coinoskobi bounded, chain-aware ve ölçeklenebilir ortak pipeline'a sahip oldu.

## Status

✅ CLOSED

---

# PHASE 3 — Risk, Opportunity & Entry Feasibility

## Amaç

Bir adaya girmenin mantıklı olup olmadığını deterministik risk ve maliyet kanıtlarıyla değerlendirmek.

## Sisteme Eklenenler

- config-driven strategy thresholds
- honeypot / sellability hard-block contract
- bounded sellability deep check
- trap / tax / transfer-control signals
- bytecode capability analysis
- MEV / sandwich exposure model
- market context binding
- unified risk/opportunity score
- score confidence
- evidence coverage
- unified advisory decision contract
- execution-cost / entry-feasibility model

## Alınan Kararlar

- Confirmed honeypot / unsellable hard-block olabilir.
- Suspicion veya UNKNOWN tek başına hard-block değildir.
- Hard-block matematiksel skordan ayrıdır.
- Matematiksel skor hard safety'yi override edemez.
- MEV context karar desteğidir; trade authority değildir.
- Execution cost modeli advisory'dir.
- Missing evidence otomatik olarak güvenli kabul edilmez.
- Live/wallet/execution authority Phase 3'e ait değildir.

## Doğrulama

- Phase 3 targeted regression: 83 PASS
- Full repository regression: 198 PASS
- Compile PASS
- config duplicate audit PASS
- no live/wallet transaction surface PASS
- unified score pure-local PASS
- unified decision pure-local PASS
- execution-cost engine pure-local PASS

## Faz Sonu Sistem Durumu

Phase 3 şu soruyu cevaplar:

**"Bu adaya girmek mantıklı mı?"**

## Sonraki Fazlara Bırakılanlar

- position lifecycle
- multi-stage TP
- runner
- adaptive protection
- DEX-native short-horizon market intelligence

## Status

✅ CLOSED

---

# PHASE 4 — Position Lifecycle

## Amaç

Pozisyona girdikten sonra pozisyonun mekanik olarak nasıl yönetileceğini belirlemek.

## Sisteme Eklenenler

### Multi-TP Contract

- TP1 ROI
- TP2 ROI
- TP3 ROI
- runner allocation
- config-driven position allocation

Final allocation:

- TP1: 20%
- TP2: 25%
- TP3: 25%
- Runner: 30%

### Position State Machine

- OPEN
- TP1_DONE
- TP2_DONE
- TP3_DONE
- RUNNER_ACTIVE
- CLOSED

Korunan kurallar:

- duplicate TP yok
- TP atlama yok
- fraction conservation
- deterministik state transition

### Protective / Monotonic Trailing Stop

- highest price geri gitmez
- protective stop aşağı gevşemez
- gap-up / gap-down davranışı
- exit-candidate contract

Ana invariant:

**new_stop >= previous_stop**

### Runner Mechanics

- runner'ın zorunlu final TP'si yok
- runner remaining position'ı taşır
- trailing protection ile izlenir
- future DEX exit intelligence kabul edecek şekilde ayrıştırılmıştır

## Alınan Kararlar

- Position mechanics ile market intelligence ayrı tutulur.
- TP allocation tek config kaynağından gelir.
- Runner kör şekilde sonsuza kadar açık kalmaz; gelecekte market intelligence ile beslenecek.
- Trailing protection long pozisyonda aşağı gevşetilemez.
- Phase 4 live execution authority vermez.

## Doğrulama

- Phase 4 targeted: 41 PASS
- Phase 0–4 connection regression PASS
- Smoke PASS
- E2E PASS
- Full regression PASS
- compile PASS
- DB integrity PASS
- scheduler speed PASS
- lifecycle local speed yaklaşık 49K+ ops/sec
- repository cleanup PASS

## Faz Sonu Sistem Durumu

Coinoskobi deterministik multi-TP + runner + monotonic protection mekaniklerine sahip oldu.

Phase 4 şu soruyu cevaplar:

**"Pozisyon mekanik olarak nasıl yönetilecek?"**

## Status

✅ CLOSED

---

# PHASE 5 — DEX Market Intelligence

## Amaç

DEX piyasasında çok kısa zaman aralıklarında gerçekte ne olduğunu gözlemlemek.

Ana prensip:

**DEX-native evidence first.**

Coinoskobi yalnız 5m / 15m / 1h candle mantığına bağlı olmayacaktır.

## Sisteme Eklenenler

### Gerçek DEX Data Baseline

- GeckoTerminal BSC gerçek veri inspection
- bounded real DEX read
- price
- liquidity
- volume
- transactions
- participation
- pool age
- market-cap / FDV context

### Native DEX Event Contracts

PancakeSwap V2:

- PairCreated
- Swap
- Sync
- Mint
- Burn

### Market Clock

Wall-clock:

- 250 ms
- 500 ms
- 1 s
- 2 s
- 5 s
- 10 s
- 30 s

Block-clock:

- 1
- 2
- 4
- 8
- 16
- 32 blocks

Swap-clock:

- 5
- 10
- 25
- 50
- 100 swaps

### Swap Flow

- buy/sell count
- buy/sell volume imbalance
- short-horizon swap flow mechanics

### Market Quality

- volume quality
- participation quality
- liquidity quality
- concentrated-volume suspicion

### Completeness Repair

Eklenen bileşenler:

- Flow Acceleration
- Wallet Flow
- Reserve Dynamics
- Price Impact
- Unified DEX Signal Bundle
- Phase 5 Stress Validation

Signal Bundle kapsar:

- flow momentum
- flow acceleration
- participation quality
- wallet concentration
- liquidity/reserve health
- price-impact context
- freshness
- coverage

## Alınan Kararlar

- Raw volume tek başına sağlıklı momentum değildir.
- Wallet activity otomatik whale/identity sonucu üretmez.
- Short-horizon sistem event + block + swap clock kullanır.
- Market signal bundle trade authority değildir.
- Observation ile execution ayrıdır.
- Phase 5 runner'ı doğrudan kapatmaz.
- Provider failure native event yokluğu anlamına gelmez.
- Native BSC Swap/Sync doğrulanmadan bu capability doğrulanmış gibi yazılmaz.

## Doğrulama

Başarılı:

- real GeckoTerminal bounded read PASS
- Phase 5 core targeted PASS
- Phase 0–5 connection regression PASS
- full regression PASS
- DB unchanged PASS
- DB integrity PASS
- completeness targeted tests: 35 PASS

Native BSC Swap/Sync validation:

İlk HTTP provider denemelerinde:

- Binance public RPC `eth_getLogs`: `-32005 limit exceeded`
- SubQuery connection: unavailable
- NodeReal chain_id=56: PASS
- NodeReal single-block `eth_getLogs`: `-32005 limit exceeded`

Bu sonuç provider capability sınırı olarak sınıflandırıldı ve native event
yokluğu olarak yorumlanmadı.

Ardından WebSocket subscription üzerinden gerçek PancakeSwap V2
WBNB/USDT native event akışı doğrulandı:

- BSC chain id: 56
- WebSocket subscription: PASS
- real Swap events: 6
- real Sync events: 6
- unknown subscribed events: 0
- unsubscribe: PASS
- DB unchanged: PASS

**Native BSC Swap/Sync evidence VALIDATED.**

## Bilinen Sınırlar

- HTTP `eth_getLogs` capability provider'a bağlıdır.
- Frequent native event observation için WebSocket subscription tercih edilir.
- Phase 5 observation authority taşır; live/wallet/execution authority taşımaz.

## Faz Sonu Sistem Durumu

Coinoskobi aggregate ve native gerçek DEX verisini short-horizon market
intelligence çekirdeği içinde işleyebilecek doğrulanmış mekaniklere sahiptir.

Completeness core tamamlanmıştır.

Native BSC Swap/Sync WebSocket evidence doğrulanmıştır.

Phase 5 şu soruyu cevaplayan gözlem çekirdeğini tamamlamıştır:

**"DEX piyasasında çok kısa horizonlarda gerçekte ne oluyor?"**

## Status

✅ CLOSED

---

# PHASE 6 — DEX Exit Intelligence

## Amaç

Phase 4 position lifecycle ile Phase 5 DEX market intelligence'ı birleştirip
runner'ın trend sağlığını değerlendirmek.

Primary question:

**"Trend hâlâ taşıyor mu; runner devam mı etmeli, korunmalı mı, çıkışa mı hazırlanmalı?"**

## Başlangıç Koşulu

Phase 5 native evidence boundary açık ve doğru şekilde sınıflandırılmış olmalı.

Phase 6 başlaması Phase 5'in eksik kanıtını gizlemez.

## Planlanan Kapsam

### 6A — Exit Intelligence Baseline

- exit-state inputs
- position-state binding
- freshness requirements
- UNKNOWN behavior
- hard-risk separation

### 6B — DEX Trend Health

Planlanan deterministik durumlar:

- STRONG
- HEALTHY
- WEAKENING
- BREAK
- UNKNOWN

Girdiler:

- swap-flow momentum
- flow acceleration
- participation quality
- volume quality
- liquidity/reserve health
- price-impact deterioration

Tek bir indikatör exit kararının sahibi olmayacak.

### 6C — Momentum Exhaustion

Örnek durumlar:

- fiyat yükseliyor fakat buy flow zayıflıyor
- fiyat yükseliyor fakat participation düşüyor
- fiyat yükseliyor fakat sell pressure artıyor
- fiyat yükseliyor fakat liquidity kötüleşiyor

### 6D — Divergence / Exit Pressure

- flow-price divergence
- participation-price divergence
- liquidity-price divergence
- sell-pressure acceleration
- exhaustion persistence
- debounce/noise protection

### 6E — Runner Health

Planlanan durumlar:

- RUNNER_HEALTHY
- RUNNER_PROTECT
- RUNNER_TIGHTEN
- RUNNER_EXIT_CANDIDATE
- RUNNER_EMERGENCY_EXIT_CONTEXT
- UNKNOWN

### 6F — Adaptive Trailing Intelligence

Strong trend:
- daha fazla breathing room

Healthy trend:
- normal trailing

Weakening:
- protection tighten

Confirmed break:
- exit candidate

Mevcut stop korunacak:

**recommended_stop mevcut korunan stop seviyesini düşüremez.**

### 6G — Risk / Exit Context

Reuse:

- sellability
- tax/transfer risk
- MEV exposure
- liquidity collapse
- execution feasibility

Hard safety trend score'dan üstün kalır.

### 6H — Runner Exit Contract

Advisory output:

- trend_health
- exhaustion_state
- runner_health
- trailing_recommendation
- exit_pressure
- evidence
- confidence
- freshness
- reasons

Authority:

- live_authority = false
- wallet_authority = false
- execution_authority = false

### 6I — Paper / Shadow Stress Validation

Senaryolar:

- clean sustained pump
- pump then exhaustion
- fake-volume pump
- whale-driven spike
- liquidity withdrawal during rise
- sharp reversal
- slow trend decay
- noisy sideways market
- new high + weakening DEX momentum

Ölçülecek:

- profit retained
- premature exits
- late exits
- maximum giveback
- runner capture
- false exit signals

### 6J — Final Validation

- Phase 0–6 E2E
- smoke
- stress regression
- performance
- freshness/UNKNOWN audit
- authority audit
- full regression
- DB integrity
- repository cleanup
- final closure

## Kapanış Kararları

Phase 6 sonunda aşağıdaki davranışlar doğrulanmış ve kilitlenmiştir:

- trend health deterministik olarak STRONG / HEALTHY / WEAKENING / BREAK / UNKNOWN üretir
- weakening ve break tek kötü tick ile kesinleştirilmez; persistence/debounce uygulanır
- momentum exhaustion fiyat ile flow/participation/liquidity ayrışmasını gözlemler
- exit pressure advisory context üretir; doğrudan çıkış emri vermez
- runner health HEALTHY / PROTECT / TIGHTEN / EXIT_CANDIDATE / EMERGENCY_EXIT_CONTEXT bağlamı üretir
- adaptive trailing mevcut korunmuş stop seviyesini aşağı çekemez
- hard sellability/liquidity/MEV/execution riskleri trend değerlendirmesinden ayrıdır ve üst güvenlik bağlamıdır
- stale veya eksik veri UNKNOWN olarak güvenli biçimde taşınır
- Phase 6 decision/paper/live/wallet/execution authority taşımaz

Phase 6 içinde kesin sayısal piyasa eşikleri gereksiz yere global sabit olarak kilitlenmemiştir;
gelecekte gerçek veri ve outcome evidence ile kalibrasyon yapılabilir.

## Beklenen Faz Sonu Durumu

Phase 6 şu soruyu cevaplayacak:

**"Runner hâlâ taşınmalı mı, koruma sıkılaştırılmalı mı, yoksa çıkış adayı mı?"**

## Kapanış Doğrulaması

Phase 6 final validation:

- Smoke: 2 PASS
- End-to-end: 20 PASS
- Phase 6 targeted: 65 PASS
- Phase 0-6 connection regression: 110 PASS
- Full regression: 339 PASS
- Compile: PASS
- Phase 6 local pipeline speed: ~416K ops/sec
- DB integrity / quick check: PASS
- Generated project junk cleanup: PASS
- decision authority: false
- paper authority: false
- live authority: false
- wallet authority: false
- execution authority: false

Phase 6 sonunda oluşturulan zincir:

Phase 5 DEX Signal Bundle
-> Exit Intelligence
-> Trend Health
-> Momentum Exhaustion
-> Divergence / Exit Pressure
-> Persistence / Debounce
-> Runner Health
-> Adaptive Trailing Recommendation
-> Risk / Exit Context
-> Runner Exit Advisory Contract

Kalıcı kararlar:

- tek kötü tick doğrudan BREAK üretmez
- weakening / break persistence ile doğrulanır
- hard safety trend değerlendirmesinden üstündür
- runner health execution emri değildir
- adaptive trailing mevcut korunan stop seviyesini düşüremez
- exit intelligence advisory-only kalır
- UNKNOWN / stale veri güvenli şekilde taşınır

## Status

✅ CLOSED

---

# PHASE 7 — Flow Confirmation & Market Regime Intelligence

## Amaç

Phase 5 DEX Market Intelligence ile Phase 6 DEX Exit Intelligence arasına
deterministik flow-confirmation ve market-regime katmanı eklemek.

Temel soru:

**"Gördüğümüz fiyat hareketi gerçek ve sürdürülebilir çoklu piyasa akışı
tarafından teyit ediliyor mu, yoksa tekil/noisy/çelişkili bir hareket mi?"**

Phase 7 observation/advisory katmanıdır.

Trade, paper, live, wallet, signing veya execution authority taşımaz.

## Planlanan Kapsam

### 7A — Flow Spread Baseline

- buy flow
- sell flow
- net flow
- flow spread
- spread velocity
- spread acceleration
- freshness / coverage / UNKNOWN contract

### 7B — Flow Confirmation

Planlanan deterministik durumlar:

- CONFIRMED
- PARTIAL_CONFIRMATION
- UNCONFIRMED
- CONFLICT
- UNKNOWN

Fiyat hareketi tek başına confirmation sayılmaz.

### 7C — Divergence / Convergence

- price ↔ flow divergence
- buy/sell flow divergence
- strengthening spread
- weakening spread
- convergence
- Phase 6 momentum-exhaustion bağlantısı

### 7D — Multi-Actor Flow Quality

- tek büyük swap trend değildir
- unique-wallet participation
- repeated multi-order flow
- wallet concentration
- SINGLE_ACTOR_SPIKE ayrımı
- whale-driven hareket ile geniş katılım ayrımı

### 7E — Flow Persistence / Noise Control

- tek tick trend oluşturmaz
- confirmation persistence
- divergence persistence
- debounce
- noise suppression
- rapid flip protection

### 7F — Market Regime

Planlanan deterministik rejimler:

- TRENDING_BULL
- TRENDING_BEAR
- CHOP
- CONFLICT
- TRANSITION
- UNKNOWN

### 7G — Direction / Flow Agreement

Birlikte değerlendirilecek kanıtlar:

- primary direction / opportunity context
- real DEX flow
- flow acceleration
- participation
- wallet flow
- liquidity / reserve
- price impact

Amaç tek bir metriğin karar vermesi değil,
bağımsız kanıtların aynı piyasa hikâyesini destekleyip desteklemediğini ölçmektir.

### 7H — Phase 5 / Phase 6 Binding

Planlanan zincir:

Phase 5 DEX Signal Bundle
-> Phase 7 Flow Confirmation
-> Market Regime
-> Phase 6 Exit Intelligence

Aynı gözlem verisi:

- giriş kalitesini değerlendirebilir
- pozisyon sırasında trend sağlığını besleyebilir
- exhaustion / exit-pressure bağlamını güçlendirebilir

Ancak Phase 7 doğrudan işlem emri üretmez.

### 7I — Stress / False-Signal Matrix

Zorunlu senaryolar:

- single whale / single actor spike
- fake pump benzeri tekil hareket
- high volume / low participation
- price up / flow down
- price up / liquidity deteriorating
- buy ve sell flow aynı yönde / choppy
- stale / incomplete evidence
- rapid regime flip
- conflicting wallet / participation evidence

### 7J — Final Validation / Closure

Phase 7 kapanmadan önce:

- targeted tests
- Phase 0-7 connection regression
- smoke
- end-to-end
- stress
- speed
- compile
- DB integrity / quick check
- generated-junk cleanup
- authority audit
- README / ROADMAP closure
- tek Phase 7 commit / push

Alt adımlarda ayrı push yapılmaz.

## Phase 7 Temel Kuralları

- DEX-native evidence first.
- Tek büyük swap gerçek trend kanıtı değildir.
- Raw volume tek başına confirmation değildir.
- Multi-actor participation daha güçlü kanıttır.
- Divergence ve convergence ayrı sinyallerdir.
- Tek tick ile trend/rejim değişmez.
- Stale veya eksik evidence UNKNOWN üretir.
- Hard safety gate'leri flow confirmation tarafından override edilemez.
- Phase 7 decision/paper/live/wallet/signing/execution authority taşımaz.
- Phase 5 ve Phase 6 davranışları gereksiz yere değiştirilmez.

## Korunan Gelecek Backlog — UNUTULMAYACAK

Aşağıdaki konular Phase 7 kapsamına dahil değildir.

Bunlar daha önce fazları gereksiz uzatmamak için ileri fazlara bırakılmış
önemli sistem katmanlarıdır ve roadmap ilerlerken kaybedilmeyecektir.

Phase 7 kapanışında ve sonraki her faz planlamasında bu liste yeniden
değerlendirilecektir.

- production-grade WebSocket / native event ingestion
- provider failover / reconnect / subscription health
- wallet / entity / whale intelligence
- smart-money / known-wallet intelligence
- adversary / scam-actor / MEV intelligence
- news / social / X / Telegram / Discord intelligence
- listing / delisting / ICO / IDO / launchpad / airdrop radar
- AI contract analyst
- AI explanation / assistant layer
- local / background AI
- learning / calibration / outcome memory
- false-positive / false-negative memory
- missed-opportunity / avoided-loss memory
- shadow simulation
- paper lifecycle / paper engine
- provider budget / paid-call / cost guard
- command center / panel intelligence
- live alerts / AI communication panel
- execution readiness
- wallet / signing / live-trade boundaries

Backlog kuralları:

1. Bu liste Phase 7 yapılacaklar listesi değildir.
2. Maddeler unutulduğu için roadmap dışına düşürülemez.
3. Phase 8-15 dağılımı şimdiden tahmin edilmez.
4. Her faz kapanışında mevcut darboğazlara göre liste tekrar değerlendirilir.
5. Bir madde yeni faza alınırsa kendi resmi faz kapsamına taşınır.
6. Backlog kaydı hiçbir execution/live/wallet/signing yetkisi oluşturmaz.

## Beklenen Faz Sonu Durumu

Phase 7 şu soruyu deterministik kanıtlarla cevaplayabilmelidir:

**"Bu hareket gerçek çoklu akış tarafından teyit ediliyor mu ve piyasa hangi
rejimde?"**

## Kapanış Doğrulaması

Phase 7 final validation:

- smoke: PASS
- end-to-end: PASS
- Phase 7 targeted: PASS
- Phase 0-7 connection regression: PASS
- full regression: PASS
- compile: PASS
- local speed: PASS
- DB integrity / quick check: PASS
- generated-junk cleanup: PASS
- authority audit: PASS

Kalıcı kararlar:

- raw volume tek başına confirmation değildir
- tek büyük swap trend değildir
- TRENDING_BULL / TRENDING_BEAR için MULTI_ACTOR kalite gerekir
- flow spread, velocity ve acceleration ayrı gözlemlenir
- divergence ve convergence ayrı sınıflandırılır
- confirmation/conflict tek tick ile kesinleşmez
- stale / incomplete evidence UNKNOWN üretir
- market regime advisory-only kalır
- hard safety gate'leri flow confirmation tarafından override edilemez

## Status

✅ CLOSED

---

# PHASE 8 — Native Event Ingestion & Provider Resilience

## Amaç

Phase 5'te doğrulanan gerçek BSC native Swap/Sync WebSocket kanıtını
sürekli, bounded ve güvenilir event-ingestion katmanına dönüştürmek.

Temel soru:

**"Native DEX event akışını kopma, tekrar, provider arızası ve stale veri
durumlarında güvenli ve sürekli biçimde nasıl taşıyacağız?"**

Phase 8 yalnız veri-alım / observation altyapısıdır.

Trade, paper, live-trade, wallet veya signing authority taşımaz.

## Planlanan Kapsam

### 8A — Native Event Ingestion Baseline

- mevcut HTTP / WSS capability inventory
- event subscription contract
- Swap / Sync topic binding
- bounded read policy
- freshness contract
- no-unbounded-getLogs rule

### 8B — WebSocket Subscription Adapter

- BSC native WSS connection
- eth_subscribe logs
- bounded pair/topic subscription
- clean unsubscribe
- normalized event output

### 8C — Connection Health / Reconnect

- disconnect detection
- heartbeat / liveness
- bounded reconnect
- backoff
- reconnect storm protection
- stale-state behavior

### 8D — Event Integrity

- duplicate suppression
- transactionHash + logIndex identity
- removed-log handling
- reorg awareness
- out-of-order protection
- malformed-event rejection

### 8E — Bounded Buffer / Backpressure

- bounded in-memory queue
- overflow policy
- freshness-first consumption
- no unbounded memory growth
- hot-path protection

### 8F — Provider Resilience / Failover

- primary / fallback provider abstraction
- provider capability state
- failure classification
- bounded failover
- no paid provider by default
- secrets never logged

### 8G — Subscription Health Readmodel

- connected / degraded / stale / disconnected
- last event time
- reconnect count
- duplicate count
- dropped / rejected count
- provider class
- freshness

### 8H — Phase 5 / 7 Binding

Native Swap/Sync stream
-> Phase 5 DEX Market Intelligence
-> Phase 7 Flow Confirmation / Market Regime
-> Phase 6 Exit Intelligence

Phase 8 yalnız event taşır ve normalize eder.

### 8I — Failure / Stress Matrix

- provider disconnect
- reconnect
- duplicated logs
- removed / reorg log
- malformed log
- stale stream
- burst load
- queue overflow
- provider failover
- unavailable fallback
- subscription timeout
- clean shutdown

### 8J — Final Validation / Closure

- targeted tests
- real bounded WSS validation
- Phase 0-8 connection regression
- smoke
- end-to-end
- failure stress
- throughput
- memory / boundedness
- compile
- DB integrity
- cleanup
- authority audit
- README / ROADMAP closure
- single Phase 8 commit / push

Alt fazlarda ayrı push yapılmaz.

## Phase 8 Temel Kuralları

- WebSocket ingestion decision authority değildir.
- Network failure event yokluğu değildir.
- Retry / reconnect bounded olmalıdır.
- Queue / buffer bounded olmalıdır.
- Duplicate / reorg handling zorunludur.
- Stale event FRESH gibi kullanılamaz.
- Unbounded eth_getLogs yasaktır.
- Paid provider varsayılan değildir.
- Secrets loglanmaz.
- Phase 8 live/wallet/signing authority açmaz.

## Korunan Gelecek Backlog — UNUTULMAYACAK

Phase 7'de korunan ileri backlog devam eder.

Phase 8'e yalnız native event ingestion ve provider resilience alınmıştır.

Kalan başlıklar korunur:

- wallet / entity / whale intelligence
- smart-money / known-wallet intelligence
- adversary / scam-actor / MEV intelligence
- news / social / X / Telegram / Discord intelligence
- listing / delisting / ICO / IDO / launchpad / airdrop radar
- AI contract analyst
- AI explanation / assistant layer
- local / background AI
- learning / calibration / outcome memory
- false-positive / false-negative memory
- missed-opportunity / avoided-loss memory
- shadow simulation
- paper lifecycle / paper engine
- provider budget / paid-call / cost guard
- command center / panel intelligence
- live alerts / AI communication panel
- execution readiness
- wallet / signing / live-trade boundaries

Phase 9-15 dağılımı şimdiden belirlenmez.

## Kapanış Doğrulaması

Phase 8 final validation:

- real bounded BSC WSS Swap/Sync: PASS
- smoke: PASS
- end-to-end: PASS
- Phase 8 targeted: PASS
- Phase 0-8 connection regression: PASS
- full regression: PASS
- compile: PASS
- event throughput: PASS
- bounded-memory stress: PASS
- DB integrity / quick check: PASS
- generated-junk cleanup: PASS
- authority audit: PASS

Kalıcı kararlar:

- native event ingestion bounded kalır
- unbounded eth_getLogs kullanılmaz
- duplicate eventler transactionHash + logIndex ile bastırılır
- removed logs reorg evidence olarak ayrı taşınır
- out-of-order eventler kabul edilmez
- reconnect / failover bounded kalır
- stale subscription Phase 5/7 input olarak kullanılamaz
- full buffer downstream input'i bloklar
- provider failure event yokluğu anlamına gelmez
- paid provider varsayılan değildir
- secrets loglanmaz
- Phase 8 decision/paper/live/wallet/signing/execution authority taşımaz

## Status

✅ CLOSED

---

# PHASE 9 — Reserved

## Amaç

Kapsam zamanı geldiğinde bir önceki fazın kapanışı sırasında planlanacak.

## Status

⏳ WAITING

---

# PHASE 10 — Reserved

## Amaç

Kapsam zamanı geldiğinde bir önceki fazın kapanışı sırasında planlanacak.

## Status

⏳ WAITING

---

# PHASE 11 — Reserved

## Amaç

Kapsam zamanı geldiğinde bir önceki fazın kapanışı sırasında planlanacak.

## Status

⏳ WAITING

---

# PHASE 12 — Reserved

## Amaç

Kapsam zamanı geldiğinde bir önceki fazın kapanışı sırasında planlanacak.

## Status

⏳ WAITING

---

# PHASE 13 — Reserved

## Amaç

Kapsam zamanı geldiğinde bir önceki fazın kapanışı sırasında planlanacak.

## Status

⏳ WAITING

---

# PHASE 14 — Reserved

## Amaç

Kapsam zamanı geldiğinde bir önceki fazın kapanışı sırasında planlanacak.

## Status

⏳ WAITING

---

# PHASE 15 — Final Roadmap Phase

## Amaç

Numaralandırılmış roadmap'in final fazıdır.

Kapsamı Phase 14 kapanışında resmi olarak planlanacaktır.

## Alınan Karar

Phase 15 mevcut numbered roadmap'in son fazıdır.

Phase 16 otomatik olarak oluşturulmaz.

Numaralı roadmap sonrasında geliştirme:

- release
- milestone
- sprint
- patch
- hotfix

modeliyle devam edebilir.

## Status

⏳ WAITING
