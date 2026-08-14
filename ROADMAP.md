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

Current Phase: **PHASE 12 — CLOSED**

Current Work: **AWAITING EXPLICIT PHASE 13 START DECISION**

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
- Phase 9: ✅ CLOSED
- Phase 10: ✅ CLOSED
- Phase 11: ✅ CLOSED
- Phase 12: ✅ CLOSED
- Phase 13: ⏳ WAITING
- Phase 14: ⏳ WAITING
- Phase 15: ⏳ WAITING

---

# MİMARİ ANAYASA

Bu kararlar fazlardan bağımsızdır.

- Sistem modüler, ölçülebilir ve sade tutulur.
- Coinoskobi'nin numaralandırılmış ana modülleri PHASE 1–15 ile sınırlıdır.
- PHASE 16, ERA, V2/V3 veya eşdeğer yeni ana roadmap zinciri açılmaz.
- Her PHASE sökülebilir, değiştirilebilir ve geliştirilebilir bir ana modüldür.
- Alt modüller düz harflerle adlandırılır: 12A, 12B, 12C ve devamı.
- Alt modül harflerinde yapay bir alfabetik üst sınır yoktur.
- Yeni harf yalnız iş gerçekten gerekliyse, bulunduğu PHASE'i somut biçimde
  geliştiriyorsa ve mevcut alt modüllerde yapılacak değişikliklerle temiz biçimde
  çözülemiyorsa açılır.
- Yeni alt modülün bağımsız kapsamı ve ölçülebilir kabul kriteri olmalıdır.
- Küçük düzeltme, test, refactor, provider ayarı veya isim değişikliği için yeni
  harf açılmaz; iş ilgili mevcut alt modül içinde tamamlanır.
- 12B1, 12B2A gibi iç içe alt numaralandırma kullanılmaz.
- Alfabenin ilerlemesi yeni bir ana PHASE anlamına gelmez.
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

# PHASE 9 — Wallet / Entity / Smart-Money Intelligence

## Amaç

Phase 8 ile güvenilir hale gelen native DEX event akışını kullanarak
wallet, entity, whale ve smart-money davranışlarını deterministik kanıt
olarak modele eklemek.

Temel soru:

**"Bu piyasa hareketine hangi wallet/entity davranışları eşlik ediyor ve
gözlenen akış geniş katılımlı mı, tekil/baskın aktör kaynaklı mı?"**

Phase 9 observation / reputation / context katmanıdır.

Wallet signing, live trade veya execution authority taşımaz.

## Planlanan Kapsam

### 9A — Wallet Evidence Baseline

- chain-aware wallet address normalization
- wallet activity evidence
- inbound / outbound flow
- buy / sell participation
- freshness
- UNKNOWN behavior
- identity guessing yasak

### 9B — Wallet Behavior Features

- repeated token interaction
- accumulation evidence
- distribution evidence
- burst activity
- dormant -> active transition
- participation frequency
- behavior evidence != identity proof

### 9C — Entity Linking

- wallet -> entity evidence
- chain-aware entity identity
- evidence confidence
- ambiguous links remain UNKNOWN
- same address cross-chain otomatik merge edilmez
- same symbol entity merge sebebi değildir

### 9D — Known Wallet / Smart-Money Registry

- known-wallet source contract
- source reliability
- source freshness
- label provenance
- known != trusted
- label != trade permission
- onchain behavior source labelini doğrulayabilir veya çürütebilir

### 9E — Whale Flow Intelligence

- large-wallet concentration
- whale inflow / outflow
- single-whale vs multi-wallet movement
- large transfer context
- CEX bridge evidence
- dust / noise filtering
- whale evidence != automatic bullish/bearish signal

### 9F — Wallet Risk / Reputation

- repeat-offender evidence
- suspicious coordination
- wallet concentration risk
- wallet/entity reputation
- evidence count / freshness
- hard evidence ile soft evidence ayrımı
- soft reputation gerektiğinde decay edebilir
- hard evidence keyfi olarak decay etmez

### 9G — Token Risk / Market Intelligence Bridge

Planlanan zincir:

Native Event Stream
-> Wallet / Entity Intelligence
-> Phase 5 Market Intelligence
-> Phase 7 Flow Confirmation / Market Regime
-> Risk / Exit Context

Kurallar:

- wallet/entity evidence context üretir
- tek başına entry izni vermez
- hard safety gate override edemez
- sellability/liquidity/execution safety üstündür
- whale label trade authority değildir

### 9H — Readmodel / Hot-Path Contract

- precomputed wallet/entity buckets
- bounded cache
- bounded readmodel
- hot path'te raw-event join yok
- hot path'te graph traversal yok
- hot path'te per-wallet ağır aggregation yok
- stale / missing cache -> UNKNOWN veya safe downgrade
- wallet intelligence hot path'i yavaşlatamaz

### 9I — Stress / False-Attribution Matrix

Zorunlu senaryolar:

- same address / different chain
- same symbol / different token
- dust attack
- single whale dominance
- coordinated small wallets
- fake known-wallet label
- stale known-wallet label
- CEX bridge ambiguity
- conflicting wallet evidence
- inactive -> sudden activity
- high-value transfer without trade context
- missing entity evidence

### 9J — Final Validation / Closure

Phase 9 kapanmadan önce:

- targeted tests
- Phase 0-9 connection regression
- smoke
- end-to-end
- wallet/entity stress matrix
- false-attribution tests
- speed / hot-path benchmark
- bounded-cache test
- compile
- DB integrity / quick check
- generated-junk cleanup
- authority audit
- README / ROADMAP closure
- single Phase 9 commit / push

Alt fazlarda ayrı commit/push yapılmaz.

## Phase 9 Temel Kuralları

- Onchain behavior evidence first.
- Known-wallet etiketi tek başına güven kanıtı değildir.
- Wallet label trade signal değildir.
- Same address cross-chain otomatik entity merge edilmez.
- Same symbol entity identity oluşturmaz.
- Tek whale hareketi geniş piyasa katılımı sayılmaz.
- Dust/noise gerçek wallet intent olarak yorumlanmaz.
- Ambiguous evidence UNKNOWN kalır.
- Hot path'te graph traversal yapılmaz.
- Hot path'te raw-event join yapılmaz.
- Stale wallet/entity evidence FRESH kabul edilmez.
- Hard safety wallet intelligence tarafından override edilemez.
- Phase 9 wallet/signing/live/execution authority taşımaz.

## Korunan Gelecek Backlog — UNUTULMAYACAK

Phase 9'a yalnız wallet / entity / whale / smart-money intelligence alınmıştır.

Kalan başlıklar sonraki faz planlamalarında korunacaktır:

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

Phase 10-15 dağılımı şimdiden belirlenmez.

## Beklenen Faz Sonu Durumu

Phase 9 sonunda Coinoskobi şu soruyu deterministik kanıtlarla
cevaplayabilmelidir:

**"Bu token çevresindeki wallet/entity davranışı ne söylüyor ve görülen
hareket geniş katılımlı gerçek akış mı, yoksa tekil/baskın/şüpheli aktör
davranışı mı?"**

## Kapanış Doğrulaması

Phase 9 final validation:

- smoke: PASS
- end-to-end: PASS
- Phase 9 targeted: PASS
- Phase 0-9 connection regression: PASS
- full regression: PASS
- compile: PASS
- wallet hot-path benchmark: PASS
- bounded readmodel/cache stress: PASS
- false-attribution matrix: PASS
- DB integrity / quick check: PASS
- DB unchanged: PASS
- generated-junk cleanup: PASS
- authority / hot-path contract audit: PASS

Kalıcı kararlar:

- wallet identity chain-aware kalır
- same address cross-chain otomatik merge edilmez
- entity linking evidence/confidence tabanlıdır
- ambiguous entity evidence UNKNOWN kalır
- known-wallet etiketi trust veya trade permission değildir
- onchain behavior source labelini destekleyebilir veya çürütebilir
- tek whale hareketi geniş katılım sayılmaz
- dust/noise wallet intent olarak yorumlanmaz
- CEX bridge yalnız bağlamsal evidence taşır
- hard reputation evidence keyfi decay etmez
- soft reputation gerektiğinde decay edebilir
- hot path yalnız precomputed bounded readmodel okur
- hot path raw-event join yapmaz
- hot path graph traversal yapmaz
- stale/missing wallet evidence safe downgrade üretir
- hard safety wallet intelligence tarafından override edilemez
- Phase 9 decision/paper/live/wallet/signing/execution authority taşımaz

## Status

✅ CLOSED

---

# PHASE 10 — Adversary / Scam-Actor / MEV Intelligence

## Amaç

Phase 8 native event ingestion ve Phase 9 wallet/entity/smart-money
intelligence üzerine adversarial actor intelligence katmanı eklemek.

Temel soru:

**"Gözlenen wallet/flow davranışının arkasında normal piyasa katılımı mı
var, yoksa sandwich, MEV, scam/rug, fake liquidity, wash trading,
sybil veya koordineli kötü aktör davranışı mı?"**

Phase 10 observation / risk / reputation / context katmanıdır.

Trade, paper, live-trade, wallet, signing veya execution authority taşımaz.

## Planlanan Kapsam

### 10A — Adversary Evidence Baseline

- chain-aware adversary evidence identity
- actor / wallet / entity evidence contract
- evidence type
- evidence count
- confidence
- freshness
- provenance
- UNKNOWN behavior
- suspicion != proof
- label != identity proof
- label != trade permission

### 10B — MEV / Sandwich Evidence

- frontrun / victim / backrun sequence evidence
- same-block proximity
- transaction ordering evidence
- price-impact relationship
- gas / priority context
- repeated sandwich pattern
- sandwich candidate classification
- normal arbitrage != automatic sandwich
- single similar transaction != MEV proof

### 10C — Scam / Rug Actor Patterns

- repeat rug association
- liquidity removal behavior
- suspicious deployer association
- suspicious funder relationship
- honeypot/scam association
- repeat token-launch behavior
- evidence confidence
- evidence freshness
- deterministic evidence before reputation escalation

### 10D — Fake Liquidity / Wash / Sybil Intelligence

- wash-trading evidence
- coordinated-wallet evidence
- fake participation evidence
- sybil-like clustering evidence
- circular-flow evidence
- repeated counterparty patterns
- apparent multi-actor vs independent multi-actor distinction
- wallet count alone != participation quality

### 10E — Sniper / Pump-Dump Actor Intelligence

- launch-sniper behavior
- coordinated early-buy evidence
- concentrated accumulation
- concentrated distribution
- synchronized dump evidence
- repeat pump/dump association
- sniper behavior != automatic malicious intent
- pump/dump label requires supporting evidence

### 10F — Adversary Risk / Reputation

- repeat-offender history
- hard evidence vs soft evidence
- evidence count
- confidence
- freshness
- reputation bucket
- hard evidence preservation
- soft suspicion decay
- conflicting evidence handling
- stale reputation safe downgrade
- UNKNOWN remains valid state

### 10G — Wallet / Entity / Market Risk Bridge

Planlanan zincir:

Native Event Stream
-> Phase 9 Wallet / Entity / Smart-Money Intelligence
-> Phase 10 Adversary Intelligence
-> Phase 5 Market Intelligence
-> Phase 7 Flow Confirmation / Market Regime
-> Risk / Exit Context

Kurallar:

- adversary evidence risk/context üretir
- adversary evidence gerektiğinde candidate'i downgrade/block edebilir
- adversary evidence entry permission vermez
- adversary label bullish/bearish signal değildir
- hard safety gate override edilemez
- sellability/liquidity/execution safety üstündür
- wallet/entity evidence ile adversary evidence birbirinden ayrılır
- conflicting evidence UNKNOWN veya safe downgrade üretebilir

### 10H — Adversary Readmodel / Hot-Path Contract

Hot path yalnız precomputed adversary state okur.

Planlanan alanlar:

- adversary_risk_bucket
- actor_evidence_count
- hard_evidence_present
- soft_evidence_score
- confidence
- freshness
- repeat_offender_state
- mev_risk
- scam_risk
- coordination_risk

Hot path'te:

- deep transaction trace YOK
- graph expansion YOK
- raw-event join YOK
- per-wallet ağır aggregation YOK
- AI inference YOK
- external fetch YOK
- provider call YOK

Kurallar:

- bounded cache
- bounded readmodel
- stale -> UNKNOWN / safe downgrade
- missing -> UNKNOWN
- adversary intelligence hot path'i yavaşlatamaz

### 10I — Adversarial Stress / False-Positive Matrix

Zorunlu senaryolar:

- normal arbitrage vs sandwich
- benign MEV-like ordering
- single whale vs attacker
- CEX wallet vs scam actor
- same funder vs same actor
- benign launch sniper
- coordinated malicious sniper group
- dust poisoning
- wash trading
- circular flow
- sybil-like wallet cluster
- fake multi-actor participation
- real independent multi-actor participation
- stale scam label
- fake adversary label
- conflicting evidence
- one-off suspicious transaction
- repeat offender
- removed/reorg event
- incomplete evidence
- missing evidence
- false attribution

Amaç:

**Kötü aktörü kaçırmamak kadar normal aktörü yanlışlıkla kötü aktör
olarak sınıflandırmamak.**

### 10J — Final Validation / Closure

Phase 10 kapanmadan önce:

- targeted tests
- Phase 0-10 connection regression
- smoke
- end-to-end
- adversary stress matrix
- MEV / sandwich false-positive tests
- scam/rug attribution tests
- wash/sybil false-attribution tests
- hot-path speed benchmark
- bounded-cache/readmodel stress
- compile
- DB integrity / quick check
- DB unchanged verification where applicable
- generated-junk cleanup
- authority audit
- hot-path contract audit
- README / ROADMAP closure
- TEST_RESULTS update
- single Phase 10 commit / push

Alt fazlarda ayrı commit/push yapılmaz.

## Phase 10 Temel Kuralları

- Suspicion proof değildir.
- Adversary label trade signal değildir.
- Tek olay repeat-offender reputation oluşturmaz.
- Tek benzer işlem sandwich/MEV kanıtı değildir.
- Normal arbitrage otomatik sandwich değildir.
- Whale olmak attacker olmak değildir.
- CEX wallet olmak scam actor olmak değildir.
- Same funder otomatik same actor değildir.
- Sniper behavior otomatik malicious behavior değildir.
- Wallet count tek başına gerçek multi-actor participation değildir.
- Hard evidence ile soft suspicion ayrı tutulur.
- Hard evidence keyfi decay etmez.
- Soft suspicion gerektiğinde decay edebilir.
- Stale adversary evidence FRESH kabul edilmez.
- Ambiguous/conflicting evidence UNKNOWN kalabilir.
- Hot path deep trace yapmaz.
- Hot path graph expansion yapmaz.
- Hot path raw-event join yapmaz.
- Hot path AI çağırmaz.
- Hot path external provider çağırmaz.
- Hard safety adversary intelligence tarafından override edilemez.
- Phase 10 decision/paper/live/wallet/signing/execution authority taşımaz.

## Korunan Gelecek Backlog — UNUTULMAYACAK

Phase 10'a yalnız adversary / scam-actor / MEV intelligence alınmıştır.

Kalan başlıklar sonraki faz planlamalarında korunacaktır:

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

Phase 11-15 dağılımı şimdiden belirlenmez.

## Beklenen Faz Sonu Durumu

Phase 10 sonunda Coinoskobi şu soruyu deterministik ve bounded evidence
ile cevaplayabilmelidir:

**"Bu hareket normal piyasa katılımından mı geliyor, yoksa MEV,
sandwich, scam/rug, wash/sybil veya koordineli adversarial actor
davranışına dair yeterli kanıt var mı?"**

Ve cevap:

- evidence tabanlı,
- false-positive kontrollü,
- freshness-aware,
- bounded,
- hot-path safe,
- authority-free

olmalıdır.

## Kapanış Doğrulaması

Phase 10 final validation:

- test collection: PASS
- smoke: PASS
- end-to-end: PASS
- Phase 10 targeted: PASS
- Phase 0-10 connection regression: PASS
- full regression: PASS
- compile: PASS
- Phase 5-10 speed matrix: PASS
- adversary hot-path benchmark: PASS
- scheduler load: PASS
- bounded event/wallet/adversary structures: PASS
- adversarial false-positive matrix: PASS
- DB integrity / quick check: PASS
- DB unchanged: PASS
- generated-junk cleanup: PASS
- authority / hot-path contract audit: PASS

Kalıcı kararlar:

- suspicion proof değildir
- adversary label trade signal değildir
- tek olay repeat-offender reputation oluşturmaz
- tek benzer işlem sandwich/MEV kanıtı değildir
- normal arbitrage otomatik sandwich değildir
- whale olmak attacker olmak değildir
- CEX wallet olmak scam actor olmak değildir
- same funder otomatik same actor değildir
- sniper behavior otomatik malicious behavior değildir
- wallet count tek başına gerçek independent participation değildir
- apparent multi-actor ve independent multi-actor ayrılır
- hard evidence ile soft suspicion ayrı tutulur
- hard evidence keyfi decay etmez
- soft suspicion gerektiğinde decay edebilir
- stale evidence FRESH kabul edilmez
- ambiguous/conflicting evidence safe downgrade veya UNKNOWN üretebilir
- hard adversary evidence candidate'i block edebilir
- elevated/high adversary evidence candidate'i downgrade edebilir
- adversary intelligence candidate'i upgrade edemez
- hard safety adversary intelligence tarafından override edilemez
- hot path yalnız precomputed bounded adversary readmodel okur
- hot path deep transaction trace yapmaz
- hot path graph expansion yapmaz
- hot path raw-event join yapmaz
- hot path heavy actor aggregation yapmaz
- hot path AI inference yapmaz
- hot path external fetch/provider call yapmaz
- Phase 10 decision/paper/live/wallet/signing/execution authority taşımaz

## Status

✅ CLOSED

---

# PHASE 11 — Learning / Calibration / Outcome Memory

## Amaç

Phase 0-10 boyunca üretilen deterministik market, flow, exit,
wallet/entity ve adversary intelligence çıktılarının zaman içinde
ne kadar doğru veya yanlış sonuç verdiğini ölçmek.

Temel soru:

**"Sistem geçmişte neyi doğru bildi, neyi yanlış alarm verdi,
neyi kaçırdı ve hangi deterministik kurallar kalibrasyon önerisi
hak ediyor?"**

Phase 11 observation / measurement / memory / proposal katmanıdır.

Trade, paper, live-trade, wallet, signing veya execution authority taşımaz.

Learning burada otomatik self-modifying sistem anlamına gelmez.

## Planlanan Kapsam

### 11A — Outcome Evidence Baseline

- chain-aware outcome identity
- candidate / observation identity
- observed_at
- evaluated_at
- expected context
- realized outcome
- evidence coverage
- freshness
- provenance
- UNKNOWN behavior
- missing outcome != success
- missing outcome != failure
- outcome evidence != trade permission

### 11B — Outcome Classification

Planlanan temel outcome sınıfları:

- VALID_SIGNAL
- FALSE_POSITIVE
- FALSE_NEGATIVE
- EXPECTED_LOSS
- AVOIDED_LOSS
- MISSED_OPPORTUNITY
- EXIT_FAILURE
- UNKNOWN

Kurallar:

- outcome deterministic evidence ile sınıflandırılır
- tek fiyat hareketi otomatik valid signal değildir
- incomplete evidence UNKNOWN kalabilir
- hindsight ile geçmiş karar yeniden uydurulmaz
- outcome classification trade authority değildir

### 11C — Signal Attribution

Phase 5-10 sinyallerinin outcome ile ilişkisini ölçer.

Kaynak aileleri:

- market intelligence
- flow confirmation
- market regime
- exit intelligence
- wallet behavior
- entity evidence
- whale flow
- wallet reputation
- MEV / sandwich
- scam / rug
- wash / sybil
- sniper / pump-dump
- adversary reputation

Kurallar:

- correlation != causation
- tek sinyal tüm outcome'un sahibi ilan edilmez
- conflicting attribution korunur
- missing attribution UNKNOWN kalır
- hard safety ile soft signal attribution ayrılır

### 11D — False-Positive / False-Negative Memory

Tutulacak memory aileleri:

- false-positive memory
- false-negative memory
- avoided-loss memory
- missed-opportunity memory
- exit-failure memory
- repeated-error memory

Bağlam:

- chain
- token
- wallet/entity
- adversary actor
- market regime
- signal family
- evidence freshness

Kurallar:

- tek hata kalıcı reputation oluşturmaz
- tekrar eden hata ayrı izlenir
- memory bounded olmak zorundadır
- memory trade authority değildir

### 11E — Calibration Statistics

Planlanan deterministik ölçüler:

- sample count
- valid signal count
- false-positive count
- false-negative count
- avoided-loss count
- missed-opportunity count
- exit-failure count
- hit ratio
- false-positive ratio
- false-negative ratio
- evidence coverage
- confidence
- freshness

Kurallar:

- minimum sample guard
- düşük sample ile güçlü calibration yok
- confidence sample büyüklüğünü dikkate alır
- stale statistics FRESH kabul edilmez
- UNKNOWN sample güvenli sample sayılmaz

### 11F — Weight / Threshold Proposal Layer

Learning katmanı yalnız öneri üretir.

Örnek proposal türleri:

- KEEP
- REVIEW
- INCREASE_WEIGHT_PROPOSAL
- DECREASE_WEIGHT_PROPOSAL
- TIGHTEN_THRESHOLD_PROPOSAL
- RELAX_THRESHOLD_PROPOSAL
- INSUFFICIENT_EVIDENCE

Kesin sınırlar:

- auto weight apply YOK
- auto threshold apply YOK
- config auto-write YOK
- strategy auto-rewrite YOK
- source-code auto-edit YOK
- hard safety weakening YOK
- AI authority YOK
- trade authority YOK

Proposal != apply.

### 11G — Outcome Decay / Evidence Windows

- recent outcome window
- medium outcome window
- long outcome window
- soft memory decay
- hard evidence preservation
- regime-aware context
- stale-memory handling

Kurallar:

- soft historical influence gerektiğinde decay edebilir
- hard evidence keyfi olarak silinmez
- eski market regime yeni regime ile eşit ağırlıkta kabul edilmez
- decay geçmiş outcome kaydını yok etmek değildir

### 11H — Learning Readmodel / Hot-Path Contract

Hot path yalnız precomputed learning/calibration bucket okur.

Planlanan alanlar:

- calibration_bucket
- sample_count
- confidence
- false_positive_ratio
- false_negative_ratio
- avoided_loss_ratio
- missed_opportunity_ratio
- freshness
- proposal_state

Hot path'te:

- raw outcome history scan YOK
- DB aggregate YOK
- graph traversal YOK
- AI inference YOK
- external fetch YOK
- provider call YOK
- automatic calibration apply YOK

Kurallar:

- bounded cache
- bounded readmodel
- stale -> UNKNOWN / safe downgrade
- missing -> UNKNOWN
- learning hot path'i yavaşlatamaz

### 11I — Learning / Calibration Stress Matrix

Zorunlu senaryolar:

- insufficient sample
- one large win
- one large loss
- repeated false positives
- repeated false negatives
- avoided-loss streak
- missed-opportunity streak
- exit failures
- conflicting outcomes
- stale outcome memory
- regime change
- survivorship bias candidate
- incomplete evidence
- missing outcome
- duplicate outcome
- out-of-order outcome
- removed/reorg evidence
- extreme outlier
- hard evidence preservation
- soft memory decay
- proposal without apply
- attempted automatic threshold change
- attempted automatic weight change

Amaç:

**Sistemin birkaç sonuca bakıp aşırı öğrenmesini engellemek ve
ölçüm katmanının karar/execution authority kazanmasını önlemek.**

### 11J — Final Validation / Closure

Phase 11 kapanmadan önce:

- targeted tests
- Phase 0-11 connection regression
- smoke
- end-to-end
- outcome classification stress
- false-positive / false-negative stress
- calibration minimum-sample tests
- regime-change tests
- survivorship-bias tests
- proposal-only authority tests
- hot-path speed benchmark
- bounded-memory/readmodel stress
- compile
- DB integrity / quick check
- DB unchanged verification where applicable
- generated-junk cleanup
- authority audit
- hot-path contract audit
- README / ROADMAP closure
- TEST_RESULTS update
- single Phase 11 commit / push

Alt fazlarda ayrı commit/push yapılmaz.

## Phase 11 Temel Kuralları

- Outcome hindsight ile yeniden yazılmaz.
- Missing outcome başarı değildir.
- Missing outcome başarısızlık değildir.
- Correlation causation değildir.
- Tek outcome calibration için yeterli değildir.
- Minimum sample guard zorunludur.
- False positive ve false negative ayrı izlenir.
- Avoided loss ve missed opportunity ayrı izlenir.
- Exit failure ayrı memory sınıfıdır.
- Hard evidence ile soft learning memory ayrıdır.
- Soft memory decay edebilir.
- Hard evidence keyfi decay etmez.
- Regime değişimi calibration context'inde korunur.
- Proposal apply değildir.
- Learning config değiştiremez.
- Learning threshold değiştiremez.
- Learning weight değiştiremez.
- Learning source code değiştiremez.
- Learning hard safety gate'i zayıflatamaz.
- Hot path raw history taramaz.
- Hot path DB aggregate yapmaz.
- Hot path AI çağırmaz.
- Hot path external provider çağırmaz.
- Phase 11 decision/paper/live/wallet/signing/execution authority taşımaz.

## Korunan Gelecek Backlog — UNUTULMAYACAK

Phase 11'e yalnız learning / calibration / outcome memory alınmıştır.

Kalan başlıklar sonraki faz planlamalarında korunacaktır:

- shadow simulation
- news / social / X / Telegram / Discord intelligence
- listing / delisting / ICO / IDO / launchpad / airdrop radar
- AI contract analyst
- AI explanation / assistant layer
- local / background AI
- paper lifecycle / paper engine
- provider budget / paid-call / cost guard
- command center / panel intelligence
- live alerts / AI communication panel
- execution readiness
- wallet / signing / live-trade boundaries

Phase 12-14 dağılımı şimdiden belirlenmez.

Phase 15 Final Roadmap Phase olarak korunur.

## Beklenen Faz Sonu Durumu

Phase 11 sonunda Coinoskobi şu soruyu deterministik evidence ile
cevaplayabilmelidir:

**"Geçmiş sinyal ve risk değerlendirmelerimiz ne kadar başarılıydı,
nerelerde yanlış alarm verdik, nereleri kaçırdık ve yeterli kanıt
varsa hangi kalibrasyon değişikliği yalnız öneri olarak incelenmeli?"**

Cevap:

- evidence-based
- bounded
- sample-aware
- freshness-aware
- regime-aware
- false-positive aware
- false-negative aware
- proposal-only
- hot-path safe
- authority-free

olmalıdır.

## Status

✅ CLOSED

---

# PHASE 12–15 — FINAL ROADMAP LOCK

## Aktif durum

- Phase 11: ✅ CLOSED
- OCR: ✅ CLOSED
- Phase 12: 🟡 ACTIVE
- Phase 13: ⏳ WAITING
- Phase 14: ⏳ WAITING
- Phase 15: ⏳ WAITING / FINAL ROADMAP PHASE
- Phase 12 başlangıç baseline: **873 PASS**
- İlk operasyonel hedef: **sistemi gerçek runtime ile tamamlayıp PAPER TRADE'e geçirmek**

Phase 12'nin ilk işi yeni özellik eklemek değil; paper trade için gerçek runtime readiness durumunu deterministik olarak ölçmek ve yalnız gerçek blocker'ları kapatmaktır.

## Roadmap sınırı

- Phase 12–15 mevcut numaralı roadmap'in son bölümüdür.
- Phase 15 final roadmap fazıdır.
- Phase 16, Era, V2 veya V3 otomatik olarak açılmaz.
- Phase 15 sonrasında gerçek kullanımda bulunan eksik, düzeltme ve iyileştirmeler ilgili fazın altında patch/hotfix/maintenance olarak yürütülür.
- Yeni numara üretmek yerine çalışan sistemi ölçmek, düzeltmek ve iyileştirmek esastır.

## Çeviklik ve güvenlik doktrini

Coinoskobi güvenli olacaktır; fakat güvenlik adına paranoyak, korkak veya hantal hale getirilmeyecektir.

- Güvenlik mümkün olduğunca basit, deterministik, ucuz ve kanıtlanmış yöntemlerle sağlanır.
- Hard block yalnız ağır ve doğrulanabilir risklerde kullanılır.
- Soft riskler otomatik hard block'a çevrilmez; score, confidence, WATCH, sizing veya manuel değerlendirme ile yönetilir.
- Hot path'e gereksiz DB aggregate, raw-history scan, AI/provider beklemesi veya tekrarlı ağır doğrulama eklenmez.
- Ağır işler bounded slow path'te; hızlı karar için gerekli veri precomputed/readmodel/cache hattında tutulur.
- Aynı riski kapsayan duplicate guard/state/pipeline oluşturulmaz.
- Yeni koruma eklenmeden önce gerçek risk, ölçüm, mevcut korumanın yetersizliği ve latency/complexity maliyeti sorgulanır.
- Paper/live evidence bir guard'ın kaliteli fırsatları gereksiz öldürdüğünü gösterirse guard gözden geçirilir, gevşetilir veya kaldırılır.
- Amaç hiç kaybetmemek değil; kötü kayıpları sınırlarken kaliteli fırsatları hızlı yakalamaktır.
- Hız güvenliğin düşmanı değildir; güvenlik hızlı mimarinin içine gömülür.

Takip edilecek önemli kalite metriği: Opportunity Kill Rate — güvenlik/filtre kararlarının sonradan kaliteli olduğu görülen kaç fırsatı gereksiz yere elediği.

---

# PHASE 12 — Operational Paper-Trade Readiness

## Status

✅ CLOSED — 2026-08-14

## Ana hedef

Sistemi gerçek kaynaklarla uçtan uca çalışır hale getirip güvenilir PAPER TRADE operasyonuna geçirmek.

Phase 12'nin başarı tanımı yeni özellik sayısı değildir. Başarı: gerçek runtime verisiyle adayın keşiften paper pozisyon kapanışına kadar aynı application lifecycle içinde izlenebilir ve tekrarlanabilir şekilde ilerlemesidir.

## İlk iş sırası

### 12A — Paper Readiness Preflight

- production composition root kontrolü
- WSS config + market-flow binding kontrolü
- paper lifecycle binding kontrolü
- paper DB/schema availability
- outcome-learning feed availability
- authority sınırlarının kapalı olduğunu doğrulama
- blocker listesi üretme
- hot path'e iş eklemeyen startup/read-only preflight

### 12B — Real Runtime Paper Smoke

12A READY olduktan sonra:

- gerçek scanner/cache candidate
- gerçek configured WSS/native context
- market/flow + actor intelligence
- risk/decision
- paper admission
- gerçek paper DB OPEN
- position manager CLOSE
- outcome → learning

aynı application lifecycle içinde doğrulanır.

### 12C — Paper Operation Start

Smoke PASS sonrası sistem kontrollü paper modunda sürekli çalıştırılır. Bu noktadan sonra Phase 12'nin ana işi yeni guard eklemek değil gerçek davranışı ölçmektir.

## Kapsam

1. Gerçek runtime kaynaklarının production composition root altında doğrulanması.
2. Scanner → ingress → bounded queue → analysis → intelligence → risk/safety → decision → paper admission → paper lifecycle zincirinin tek akışta çalışması.
3. WSS/native event, market/flow ve wallet/entity/adversary context'in paper kararına doğru bağlanması.
4. Paper entry/exit lifecycle'ın gerçek opening context ile kayıt altına alınması.
5. SL/TP, trailing/exit, sellability/liquidity ve execution-cost varsayımlarının paper sonuçlarında korunması.
6. Paper outcome → Phase 11 learning feed zincirinin gerçek paper kapanışlarıyla beslenmesi.
7. Restart/recovery, bounded memory, DB integrity ve runtime health doğrulaması.
8. Provider/cost bütçesi: local/cache/free-first; pahalı çağrı bounded ve gerekçeli.
9. Minimum operability görünürlüğü: hangi token, neden aday, giriş var mı, engel ne, SL/TP, beklenen maliyet/PnL, paper sonucu.
10. Gereksiz script/artifact/log üretmeden temiz runtime işletimi.

## Phase 12 altında sonra bakılacaklar

### Honeypot.is provider hardening

Honeypot.is sellability, honeypot ve buy/sell/transfer tax kanıtı için korunur.
Çok yeni tokenlarda görülen `404` / indeksleme gecikmesi, tek adayı zorlayarak
Phase 12B akışını dağıtmadan daha sonra Phase 12 altında değerlendirilecektir.

İncelenecek başlıklar:

- pair parametreli ve pair parametresiz sorgu davranışı
- yeni-token indeksleme gecikmesi
- bounded retry ve cache
- UNKNOWN sonucunun paper admission etkisi
- gerekirse Alchemy/NodeReal on-chain evidence veya alternatif provider

Bu çalışma ilk gerçek paper lifecycle E2E'yi gereksiz yere bloke etmez; missing
evidence güvenli kabul edilmez ve provider hot path'e taşınmaz.

## Phase 12 sınırları

- Gerçek para YOK.
- Wallet signing YOK.
- Live execution YOK.
- Learning auto-apply YOK.
- AI authority YOK.
- Paper trade gerçek runtime evidence ile çalışabilir.

## Phase 12 kapanış kriteri

Sistem yeterli süre gerçek runtime altında stabil çalışır; paper trade açar/kapatır; sonuçları outcome memory/learning hattına taşır; restart/recovery ve DB bütünlüğünü korur; hot path ölçümlerinde kabul edilemez hantallık görülmez. Bundan sonra ana çalışma paper sonuçlarını toplamaya geçer.

## Phase 12 kapanış kanıtı — 2026-08-14

- 12A production composition root, WSS/market-flow, paper lifecycle, DB/schema,
  outcome-learning feed ve authority sınırlarıyla PASS.
- 12B gerçek scanner/cache adayı, on-chain doğrulanmış multi-pair WSS,
  market/flow ve actor intelligence, risk/decision, paper admission, gerçek
  PAPER OPEN, doğal CLOSE ve outcome-learning zinciriyle PASS.
- 12C application-owned systemd runtime, dinamik WSS pair yenileme, bounded
  scanner cache, bounded open-position fiyat yenileme, atomic paper position
  limiti ve operability loglarıyla PASS.
- Gerçek kapanış örneklerinde `VALID_SIGNAL` ve `FALSE_POSITIVE`
  sınıflandırmaları üretildi; evidence coverage `1.0` oldu ve olumsuz sonuçlar
  bounded outcome memory'ye yazıldı.
- Provenance düzeltmesinden sonraki paper girişlerinde pool ve quote token
  opening context içinde entry anında kalıcılaştırıldı.
- Restart/recovery, tek runtime PID, `NRestarts=0`, runtime error/warning
  sayılarının sıfır olması ve açık pozisyon fiyat recovery akışı doğrulandı.
- Tam regresyon: `897 passed`; bilinen tek uyarı `websockets.legacy`
  deprecation uyarısıdır.
- Paper ve cache SQLite integrity/quick kontrolleri `ok`.
- Gerçek para, wallet signing, live execution, learning auto-apply ve AI
  authority kapalı kaldı.

Phase 13 otomatik açılmaz; başlangıcı ayrı ve açık kullanıcı kararı gerektirir.

---

# PHASE 13 — Paper Outcome Learning & Calibration

## Ana hedef

Phase 12'de oluşan gerçek paper sonuçlarını kullanarak sistemin nerede iyi, nerede kötü karar verdiğini ölçmek ve fırsat kaçırma/kötü işlem dengesini iyileştirmek.

## Kapsam

- VALID_SIGNAL / FALSE_POSITIVE / FALSE_NEGATIVE / AVOIDED_LOSS / MISSED_OPPORTUNITY / EXIT_FAILURE gerçek outcome analizi.
- False-negative ve missed-opportunity özellikle korunur; sistem yalnız kayıptan korkmayı öğrenmez.
- Opportunity Kill Rate ve avoided-loss dengesi ölçülür.
- Entry/exit, SL/TP, sellability, liquidity, gas, slippage, MEV ve quote-delay etkileri değerlendirilir.
- Market regime, wallet/entity, adversary ve flow attribution sonuçlarla karşılaştırılır.
- Calibration/threshold/weight değişiklikleri proposal-only kalır; yeterli sample olmadan güçlü değişiklik yapılmaz.
- Memory bounded/TTL/rolling-window/pruning ile tutulur; hot path şişirilmez.

## Kapanış kriteri

Yeterli paper evidence ile tekrarlanan hata/fırsat kaçırma sınıfları görünür hale gelir ve uygulanacak değişiklikler ölçülebilir proposal olarak üretilebilir.

---

# PHASE 14 — Command Center & AI Analyst

## Ana hedef

Operatörün birkaç saniyede "hangi token, giriş var mı, neden, SL/TP nerede, vur-kaç uygun mu, paper sonucu ne, engel ne, onay gerekiyor mu?" sorularını cevaplayabildiği kapalı Command Center oluşturmak.

## Kapsam

- Candidate fırsat listesi ve önceliklendirme.
- Atış Poligonu paper/simulation görünümü.
- Vur-Kaç tactical görünümü.
- Entry plan, exit plan, SL/TP, risk/reward ve net expected PnL.
- Gas/slippage/MEV/exit-cost ve sellability/liquidity görünürlüğü.
- Flow, wallet/entity, adversary, news/social/launch context'in sade karar özeti.
- News/social/X/Telegram/Discord, listing/delisting, ICO/IDO/launchpad/airdrop radarının bounded ve source-trust kontrollü entegrasyonu; hot path bu kaynakları beklemez.
- AI contract analyst ve panel assistant: açıklar, uyarır, soruları cevaplar, özetler ve proposal üretir.
- Local/free/cache-first AI; pahalı model yalnız gerçekten değerli ağır analizde.
- AI trade/sign/apply/hardblock-override authority taşımaz.

## Kapanış kriteri

Panel karar desteğini sade ve hızlı verir; paper/runtime truth ile uyumludur; AI açıklayıcı/analisttir, otorite değildir; UI veya AI hot path'i yavaşlatmaz.

---

# PHASE 15 — Final Operational Validation & Controlled Micro-Live

## Ana hedef

Paper varsayımları ile gerçek execution koşulları arasındaki farkı ölçmek ve yalnız açık kullanıcı onayıyla çok küçük kontrollü gerçek para doğrulamasına hazırlanmak/uygulamak.

## Kapsam

- Simulation Drift Validator: theoretical/paper PnL ile gerçekçi gas, slippage, fill, quote delay ve execution timing karşılaştırması.
- Signal-to-block latency/time-drift guard: haber/social sinyali geldiğinde onchain durumun çoktan değişip değişmediğinin kontrolü.
- Paper → micro-live drift ölçümü.
- Entry/exit başarısı, sellability, realized slippage, gas, MEV ve execution latency ölçümü.
- Çok küçük sermaye, açık limitler ve kill-switch.
- Wallet/signing/live authority yalnız bu fazda, ayrı açık kullanıcı onayıyla ve minimum kapsamla açılabilir.
- Paper ve live sonuçları ayrı tutulur; live sonuç paper varsayımını kalibre etmek için evidence olur.
- Gerçek kullanımda çıkan düzeltmeler ilgili faz altında patch/hotfix olarak yapılır; yeni faz açılmaz.

## Final kapanış kriteri

Coinoskobi gerçek veriyle çalışan, paper sonuçlarıyla öğrenen, operatöre hızlı karar desteği veren ve gerçek execution davranışı ölçülmüş bir sistemdir. Phase 15 kapanınca numbered roadmap kapanır.

---

# Uygulama sırası

Şu anki tek aktif hedef **PHASE 12**'dir.

Öncelik sırası:

1. Runtime truth ve production composition doğrulaması.
2. Uçtan uca paper-trade readiness.
3. Gerçek paper trade başlatma.
4. Yeterli outcome toplama.
5. Phase 13 learning/calibration.
6. Phase 14 Command Center/AI.
7. Phase 15 final operational validation ve yalnız açık onayla micro-live.

Bir sonraki faz, mevcut fazın kapanış kriterleri gerçekten sağlanmadan açılmaz.

---

# OCR — Operational Closure Repair

> **OCR = Operational Closure Repair**
>
> Optical Character Recognition değildir.

## OCR'nin Rolü

OCR yeni bir Phase değildir.

Amaç:

- Phase 0–11 boyunca yapılmış repair/audit çalışmalarını tek yerde toplamak
- gerçek runtime entegrasyon açıklarını kapatmak
- geçici R-numaralı repair zincirini sona erdirmek
- Phase 12 öncesi operational closure yapmak

Kurallar:

- Phase 12 açılmaz
- Phase 12 numarası tüketilmez
- yeni R1/R2/R3... isimleri üretilmez
- bundan sonraki tüm repair işleri OCR altında tutulur
- disposable scriptler roadmap'e yazılmaz
- yalnız kalıcı değişiklik + neden + sonuç kaydedilir
- OCR tamamen kapanana kadar ara commit/push yapılmaz
- finalde tek OCR validation + tek commit + tek push yapılır

Current Phase:

**PHASE 11 — CLOSED**

Next Phase:

**PHASE 12 — RESERVED**

OCR Status:

**✅ CLOSED**

---

## Neden OCR Açıldı?

Phase 11 kapanışı sonrası bağımsız Codex mimari denetimi yapıldı.

Denetim baseline:

- Engineering Quality: **68/100**
- Production Readiness: **45/100**
- Phase 12 Gate: **B**
- P0 Critical: **0**

Ana sonuç:

Sistem library/code/test seviyesinde güçlüydü fakat bazı Phase 5–11
bileşenleri gerçek application runtime'ında eksiksiz beslenmiyor veya
lifecycle tarafından sahiplenilmiyordu.

OCR'nin amacı puan şişirmek değildir.

Amaç:

**bir sonraki adversarial audit aynı operational açıkları tekrar
bulamayacak kadar gerçek bağlantıları tamamlamaktır.**

---

# Phase 0–11 Kısa Tarihçe

| Faz | Ne yapıldı? | Neden? | Sonuç |
|---|---|---|---|
| Phase 0 | Temel bug/cache/scanner temizliği | Botu çalışır ve test edilebilir yapmak | Temel sistem stabil hale geldi |
| Phase 1 | Runner/logger/config/paper DB/WAL | Temiz core altyapı | Sade çekirdek oluştu |
| Phase 2 | Bounded queue/cache/conveyor/scheduler | Ölçeklenebilir pipeline | Chain-aware bounded pipeline oluştu |
| Phase 3 | Risk/sellability/MEV/cost/advisory scoring | Güvenli giriş fizibilitesi | Hard safety score'dan ayrıldı |
| Phase 4 | Multi-TP/runner/trailing lifecycle | Pozisyon mekanikleri | Deterministik lifecycle oluştu |
| Phase 5 | DEX market intelligence/native evidence | Kısa horizon piyasayı görmek | DEX-native gözlem çekirdeği oluştu |
| Phase 6 | Exit intelligence/runner health | Çıkış bağlamı üretmek | Trend/exit intelligence oluştu |
| Phase 7 | Flow confirmation/regime | Tek sinyale bağımlılığı azaltmak | Flow/regime context oluştu |
| Phase 8 | Native event ingestion | DEX eventlerini normalize etmek | Bounded event contract oluştu |
| Phase 9 | Wallet/entity/smart-money | Cüzdan ve entity davranışı | Wallet/entity intelligence oluştu |
| Phase 10 | Adversary/MEV/scam | Manipülasyon/kötü aktör ayrımı | Adversary intelligence oluştu |
| Phase 11 | Outcome/calibration/memory | Hata ve başarıyı ölçmek | Proposal-only safe learning oluştu |

---

# OCR Geçmiş Repair Kayıtları

Aşağıdaki R isimleri tarihsel kayıttır.

**Bundan sonra yeni R numarası açılmaz.**

## Historical R1 — Versioned Paper Schema

### Neydi?

Paper DB clean-start/schema contract yeterince açık değildi.

### Neden yapıldı?

Yeni veya boş DB'nin güvenli ve deterministik kurulması gerekiyordu.

### Sonuç

✅ TAMAMLANDI

- versioned paper schema
- clean-start temp DB PASS
- idempotent schema creation
- integrity/quick check PASS
- production DB unchanged

---

## Historical R2 — SQLite Concurrency / Atomic Insert

### Neydi?

Shared SQLite connection üzerinde eşzamanlı paper insert yarış riski vardı.

### Neden yapıldı?

Aynı process içinde duplicate OPEN ve transaction yarışlarını engellemek.

### Sonuç

✅ TAMAMLANDI

- RLock
- serialized DB access
- BEGIN IMMEDIATE
- atomic check + insert
- rollback
- WAL/busy timeout
- thread concurrency stress PASS
- production DB unchanged

### OCR'de kalan konu

DB-level uniqueness hâlâ ayrıca tamamlanacak.

---

## Historical R3 — O(1) Readmodels / Streamed Scheduler

### Neydi?

Wallet/adversary readmodel eviction ve scheduler memory davranışı
uzun runtime için iyileştirilmeliydi.

### Neden yapıldı?

Hot path üzerinde O(n) büyümeyi ve gereksiz memory amplification'ı azaltmak.

### Sonuç

✅ TAMAMLANDI

- deque tabanlı O(1) eviction
- wallet readmodel bounded
- adversary readmodel bounded
- streamed scheduler
- pressure benchmark PASS
- 50K scheduler load PASS

---

## Historical R4 — Operational Bounded WSS Runtime

### Neydi?

WSS contracts vardı fakat operational connect/subscribe/recv/reconnect
runtime eksikti.

### Neden yapıldı?

Native event ingestion için gerçek bounded runtime davranışı gerekiyordu.

### Sonuç

✅ IMPLEMENTED / TESTED

- modern websockets asyncio API
- connect / subscribe / receive
- bounded event buffer
- bounded duplicate memory
- timeout
- reconnect/backoff
- maximum reconnects
- unsubscribe
- cancellation/shutdown
- malformed/disconnect tests
- reconnect stress PASS

### OCR'de kalan konu

Application lifecycle wiring + reorg/delivery correctness tamamlanacak.

---

## Historical R5 — Runtime Intelligence Composition

### Neydi?

Phase 5–10 intelligence modülleri gerçek PipelineEngine ile yeterince
bağlı değildi.

### Neden yapıldı?

Market/wallet/adversary context'in ortak runtime composition üzerinden
pipeline'a taşınması gerekiyordu.

### Sonuç

✅ STRUCTURAL INTEGRATION TAMAMLANDI

- RuntimeIntelligenceComposition
- PipelineEngine binding
- lazy initialization
- backward compatibility
- market_context mutation bug düzeltildi
- runtime intelligence targeted tests PASS

### OCR'de kalan konu

Ordinary run_cycle gerçek market/flow/wallet/adversary evidence ile
beslenecek.

---

## Historical R6 — Integration / Failure / Long-Run Seal

### Neydi?

R1–R5 değişikliklerinin tek tek test geçmesi yeterli değildi.

### Neden yapıldı?

Long-run, scheduler, readmodel, DB concurrency ve integration birlikte
doğrulanmalıydı.

### Sonuç

✅ TAMAMLANDI

- integration tests
- failure-path validation
- 1M readmodel long-run
- scheduler 100K PASS
- repeated paper concurrency PASS
- DB integrity/quick PASS
- authority audit PASS
- compile PASS

---

## Historical R7 — Dependency / Legacy / Reproducibility

### Neydi?

requirements unpinned idi ve websockets legacy warning kaynağı belirsizdi.

### Neden yapıldı?

Kurulumun tekrar üretilebilir olması ve warning'in proje mi dependency mi
olduğunun ayrılması gerekiyordu.

### Sonuç

✅ TAMAMLANDI

Pinned direct dependencies:

- web3==7.16.0
- python-dotenv==1.2.2
- requests==2.34.2
- loguru==0.7.3
- pytest==9.1.1

Doğrulamalar:

- clean temp venv install PASS
- clean import smoke PASS
- project-owned legacy websocket import ZERO
- project WSS modern asyncio API
- websockets.legacy warning = Web3 dependency-owned

### Bilinen sınır

Transitive dependency graph henüz hash-lock değildir.

---

## Historical R8 — Phase 0–10 Closure Repair Final Audit

### Neydi?

Önceki repair'lerin gerçekten birlikte çalıştığını doğrulamak gerekiyordu.

### Neden yapıldı?

Phase 11'e dönmeden önce Phase 0–10 repair zincirini mühürlemek.

### Sonuç

✅ TAMAMLANDI

- full regression PASS
- persistence repair PASS
- runtime composition PASS
- WSS contract PASS
- hot-path/scheduler PASS
- dependency reproducibility PASS
- DB health/unchanged PASS
- authority zero PASS

Codex finding classification:

FIXED:
- clean-start paper schema
- SQLite thread concurrency
- O(1) readmodels
- scheduler memory behavior
- bounded WSS implementation
- runtime composition structure
- direct dependency pinning

---

## Historical R9A — Candidate Queue Strict Boundedness

### Neydi?

Candidate `_entries` bounded idi fakat stale heap entries ve cooldown map
yardımcı state'i uzun runtime'da büyüyebiliyordu.

### Neden yapıldı?

Continuous observation sırasında hidden auxiliary memory growth
oluşmasını engellemek.

### Sonuç

✅ TAMAMLANDI

- heap compaction
- expired cooldown pruning
- explicit auxiliary limits
- 1M duplicate heap stress PASS
- cooldown churn stress PASS
- existing priority ordering preserved
- existing cooldown behavior preserved
- full regression PASS

Bu işten itibaren R numaralandırması sona ermiştir.

---

# OCR Aktif İş Listesi

## 1. Candidate Queue Strict Boundedness

Status: ✅ TAMAMLANDI

Sonuç:

- active queue bounded
- best/worst heaps bounded
- cooldown state pruned/bounded
- 1M duplicate stress PASS

---

## 2. DB-Level Single OPEN Guarantee + Migration

Status: ✅ TAMAMLANDI

### Neydi?

Process-local RLock ve BEGIN IMMEDIATE güvenliydi ancak farklı
process'lerin aynı token için eşzamanlı OPEN kayıt üretmesini
database seviyesinde engelleyen invariant yoktu.

### Neden yapıldı?

Thread-safe olmak multi-process safe olmak değildir.
Tek OPEN position garantisinin uygulama koduna değil SQLite'ın
kendisine ait olması gerekir.

### Sonuç

- paper schema v2
- case-insensitive partial unique OPEN index
- DB-level single OPEN invariant
- clean v1 → v2 migration PASS
- idempotent migration PASS
- legacy duplicate preflight guard PASS
- duplicate legacy data otomatik değiştirilmez
- newer-schema rejection korunuyor
- closed history yeni OPEN'i engellemiyor
- multiprocess contention PASS
- gerçek DB preflight PASS
- SQLite-consistent pre-migration backup PASS
- gerçek DB schema v2 migration PASS
- integrity / quick check PASS
- process race sonrası IntegrityError güvenli duplicate sonucu üretir

Unique invariant:

`lower(token)` başına `status='OPEN'` için en fazla 1 row.

Bu garanti artık yalnız process lock ile değil database seviyesinde
uygulanmaktadır.

---

## 3. WSS Delivery / Subscription / Reorg Correctness

Status: ✅ TAMAMLANDI

### Neydi?

WSS runtime bounded ve reconnect-safe idi fakat correctness tarafında
üç ana açık vardı:

- event callback başarısız olmadan önce local seen/accepted state
  güncelleniyordu
- notification subscription ID aktif subscription ile doğrulanmıyordu
- removed/reorg event daha önce seen olmuşsa duplicate olarak
  yutulabiliyordu

İlk düzeltmede retraction normal `on_event` callback kanalına
gönderildi ve mevcut callback contract regression üretti.

### Neden yapıldı?

Native event runtime şu garantileri taşımalıdır:

- downstream callback failure event kaybı üretmemeli
- stale/foreign subscription event'i kabul edilmemeli
- reorg canonical state correction üretmeli
- mevcut normal-event callback contract bozulmamalı
- correction ve canonical-event yolları birbirinden ayrılmalı

### Sonuç

✅ Delivery correctness tamamlandı.

- callback-before-ack semantics
- callback failure sonrası event seen/accepted sayılmaz
- reconnect replay mümkün
- explicit callback `False` negative acknowledgement
- active subscription ID validation
- stale/foreign subscription rejection
- removed/reorg duplicate kontrolünden önce sınıflandırılır
- successful removal `RETRACTION` üretir
- successful retraction seen identity'yi kaldırır
- retraction sonrası ordering watermark güvenli reset edilir
- canonical replay yeniden kabul edilir
- failed retraction state'i yanlışlıkla temizlemez
- normal event callback: `on_event`
- reorg correction callback: `on_retraction`
- historical `on_event` contract korunmuştur
- bounded seen/buffer korunmuştur
- authority zero korunmuştur
- exact failed regression recheck PASS
- WSS targeted: 39 PASS
- full regression: 813 PASS
- compile PASS
- diff check PASS

Delivery modeli:

`CALLBACK_BEFORE_ACK_AT_LEAST_ONCE`

Bu model exactly-once iddiası taşımaz.

Downstream consumers event identity ile idempotent davranmalıdır.

Normal callback contract:

`on_event` → canonical accepted events only

Correction callback contract:

`on_retraction` → reorg/retraction events only

---

## 4. Application-Owned WSS Lifecycle

Status: ✅ TAMAMLANDI

### Neydi?

NativeWSSRuntime implement ve test edilmişti fakat gerçek
application composition root tarafından sahiplenilmiyordu.

`main.py → Runner` yalnız scheduler loop çalıştırıyor;
WSS startup/shutdown lifecycle dışarıda kalıyordu.

### Neden yapıldı?

Operational component olabilmesi için WSS runtime:

- application tarafından oluşturulmalı
- startup sırasında başlatılmalı
- SIGINT/SIGTERM shutdown sırasında durdurulmalı
- scheduler/runtime exception durumunda cleanup görmeli
- health/status görünür olmalı
- config yoksa sahte/default provider ile başlamamalı

### Sonuç

- `NativeWSSService` application-owned lifecycle wrapper
- dedicated bounded background thread
- dedicated asyncio event loop
- idempotent start
- bounded stop/join
- runtime request_stop propagation
- failure/status visibility
- generic Runner service ownership
- Runner startup service binding
- Runner finally-based shutdown
- scheduler failure sonrası service cleanup
- main.py composition root artık configured WSS service'i Runner'a bağlar
- explicit `WSS_URL`
- explicit `WSS_PAIR`
- fake/default WSS endpoint YOK
- WSS yalnız gerçek config varsa aktif
- normal application composition test edildi
- repeated start/stop stress PASS
- WSS authority zero korunuyor
- full regression PASS

Önemli sınır:

Bu madde WSS lifecycle ownership'i tamamlar.

WSS eventlerinin gerçek market/flow/wallet/adversary intelligence
producer zincirine bağlanması bir sonraki OCR işidir.

---

## 5. Real Market / Flow Runtime Feed

Status: ✅ TAMAMLANDI

### Neydi?

Ordinary `run_cycle()` yalnız liquidity/trade-size/impact/slippage
context üretiyor; RuntimeIntelligenceComposition gerçek
market/flow evidence beklemesine rağmen Phase 5–7 çoğunlukla
manual/synthetic input ile test ediliyordu.

WSS normalizer ayrıca raw log `address/data/topics` bilgisini
korumadığı için gerçek Swap direction çözümlenemiyordu.

### Neden yapıldı?

Implemented/tested intelligence ile operational intelligence aynı şey
değildir.

Phase 5–7 ordinary runtime tarafından gerçek source evidence ile
beslenmelidir.

### Sonuç

- WSS normalized event raw address/data/topics provenance taşır
- deterministic V2 Swap decoder
- explicit pair/token/quote registration
- target token yönü yalnız kayıtlı metadata ile çözülür
- metadata yoksa direction tahmin edilmez
- scanner gerçek USD volume/liquidity/price evidence sağlar
- native WSS gerçek directional Swap count sağlar
- real buyers/sellers actor evidence
- real tx count
- real flow coverage
- bounded per-pair native observation store
- reorg RETRACTION observation'ı store'dan kaldırır
- ordinary run_cycle runtime feed snapshot kullanır
- `market_intelligence` real scanner/runtime evidence ile dolar
- `flow_intelligence` yalnız gerçek directional evidence varsa dolar
- fake sell-flow YOK
- raw token amount → USD dönüşümü YOK
- missing evidence → UNKNOWN
- application composition root WSS callbacks'i PipelineEngine'e bağlar
- WSS target token explicit config ile tanımlanır
- WSS token yoksa direction tahmin edilmez
- 250K bounded native flow stress PASS
- targeted tests PASS
- full regression PASS
- authority zero korunur

Operational data path:

`WSS → normalize → callback-before-ack → PipelineEngine
→ RuntimeMarketFlowStore → build_market_context
→ RuntimeIntelligenceComposition`

Scanner market data path:

`scanner/cache → Candidate → build_market_context
→ market_intelligence`

Bu madde Phase 5–7 real runtime producer/consumer bağlantısını kapatır.

---

## 6. Real Wallet / Entity / Adversary Producers

Status: ✅ TAMAMLANDI

### Neydi?

Phase 9–10 wallet/entity/adversary classifier ve readmodel'ları
implement ve test edilmişti fakat ordinary runtime tarafından gerçek
actor identity ile beslenen producer zinciri eksikti.

Swap log `sender` alanını doğrudan kullanıcı wallet'ı kabul etmek
semantik olarak güvenli değildir; router/caller olabilir.

### Neden yapıldı?

Operational wallet intelligence gerçek chain evidence kullanmalıdır.

Wallet identity tahmin edilmemeli ve adversary risk, bulunmayan
scam/MEV/pump-dump kanıtı ile şişirilmemelidir.

### Sonuç

- bounded tx-hash → tx.from resolver
- gerçek wallet identity kaynağı yalnız transaction.from
- Swap sender/recipient wallet identity olarak kullanılmaz
- successful tx lookup bounded cache'e alınır
- repeated tx lookup provider'a tekrar gitmez
- provider failure → UNKNOWN
- provider failure güvenli wallet üretmez
- resolver cache bounded
- native event → real tx.from
- tx.from → wallet evidence
- wallet behavior
- conservative self-only entity context
- cross-wallet auto merge YOK
- institutional/entity identity claim YOK
- minimum-sample concentration guard
- wallet reputation
- runtime participation/wash-sybil context
- scam evidence uydurma YOK
- MEV evidence uydurma YOK
- pump-dump evidence uydurma YOK
- hard evidence uydurma YOK
- adversary evidence/reputation
- WalletReadModel gerçek runtime producer tarafından güncellenir
- AdversaryReadModel gerçek runtime producer tarafından güncellenir
- latest real actor ordinary run_cycle context'e bağlanır
- reorg RETRACTION actor evidence'i geri alır
- son evidence retracted ise wallet context safe-not-ready olur
- adversary context UNKNOWN'a döner
- actor event store bounded
- resolver bounded
- 100K actor stress PASS
- targeted tests PASS
- full regression PASS
- authority zero korunur

Operational actor path:

`WSS Swap
→ tx hash
→ bounded transaction resolver
→ real tx.from
→ wallet evidence / behavior
→ self-only entity context
→ conservative reputation
→ adversary context
→ WalletReadModel + AdversaryReadModel
→ RuntimeIntelligenceComposition`

Kimlik sınırı:

`TRANSACTION_FROM_ONLY`

Bu OCR maddesi cross-wallet/entity clustering yapmaz.
Bu yalnız gerçek wallet observation ve conservative runtime context'tir.

---

## 7. Paper Outcome → Phase 11 Learning Feed

Status: ✅ TAMAMLANDI

### Yapılacak

- completed paper lifecycle outcome event
- immutable outcome identity
- outcome evidence
- classification
- attribution
- bounded outcome memory
- calibration statistics
- proposal
- calibration readmodel

Korunan sınır:

- proposal != apply
- automatic weight apply YOK
- automatic threshold apply YOK
- config write YOK
- source-code rewrite YOK
- hard-safety weakening YOK
- execution authority YOK

### Başarı kriteri

Phase 11 sentetik test dışında gerçek paper outcome ile çalışmalı.

---

## 8. True Composition-Root E2E

Status: ⬜ BEKLİYOR

Gerçek zincir:

Application lifecycle
→ WSS/native event
→ market/flow aggregation
→ wallet/entity/adversary
→ PipelineEngine
→ risk/strategy
→ paper lifecycle
→ outcome
→ learning

### Başarı kriteri

FakeWS + ayrı synthetic dictionaries ile yan yana test değil;
aynı gerçek composition root içinden veri akışı kanıtlanmalı.

---

## 9. Persistence / Migration Hardening

Status: ⬜ BEKLİYOR

### Yapılacak

- ordered schema migrations
- constraints
- NOT NULL/CHECK değerlendirmesi
- old DB upgrade
- newer DB rejection korunması
- explicit PaperDatabase lifecycle/close
- backup/recovery policy

---

## 10. Failure / Recovery Hardening

Status: ⬜ BEKLİYOR

Test edilecek:

- provider timeout
- provider disconnect
- malformed RPC
- WSS disconnect
- reconnect exhaustion
- callback failure
- reorg
- DB lock
- duplicate multi-process insert
- corrupt/old DB
- queue overload
- worker failure
- restart
- SIGTERM/SIGINT

---

## 11. Operability / Observability

Status: ⬜ BEKLİYOR

Değerlendirilecek:

- startup validation
- health state
- provider health
- runtime counters
- structured logging
- DB recovery
- deployment placeholders
- Dockerfile/docker-compose gerçek ihtiyaç
- restart policy

Bu alan gereksiz mikroservis veya ağır monitoring stack eklemek için
kullanılmaz.

---

## 12. OCR Final Quality Seal

Status: ⬜ BEKLİYOR

Kapanış testleri:

- full regression
- smoke
- true E2E
- clean-start DB
- migration tests
- multi-process DB contention
- WSS reconnect/reorg/callback tests
- scheduler 100K+
- candidate queue 1M+
- readmodel 1M+
- long-run memory/soak
- speed matrix
- DB integrity/quick
- authority audit
- generated-junk cleanup
- documentation truth audit

Ardından:

1. tek OCR commit
2. tek OCR push
3. bağımsız adversarial audit
4. yeniden puanlama
5. Phase 12 gate değerlendirmesi

---

# OCR Kapanış Kriterleri

OCR ancak aşağıdakilerin tamamı sağlanırsa CLOSED olur:

- [x] Candidate queue tüm yardımcı state ile bounded
- [x] DB-level single OPEN guarantee
- [x] Tested schema migration path
- [x] WSS delivery acknowledgement güvenli
- [x] Reorg/retraction state correction
- [x] Application-owned WSS lifecycle
- [x] Real market/flow runtime feed
- [x] Real wallet/entity/adversary producer
- [x] Real paper outcome → learning feed
- [x] True composition-root E2E
- [x] Multi-process DB contention PASS
- [x] Restart/recovery tests PASS
- [x] Long-running bounded-memory soak PASS
- [x] Full regression PASS
- [x] Authority boundary unchanged
- [x] Documentation truth audit PASS
- [x] Phase 12 remains RESERVED
- [x] Independent re-audit complete

---

# OCR Terminoloji Kuralı

Bundan sonra:

Eski:

- R1
- R2
- R3
- R4
- R5
- R6
- R7
- R7A
- R8
- R9A

yalnız tarihsel referans olarak kullanılır.

Yeni işlerde:

**OCR — <iş adı>**

kullanılır.

Örnek:

`OCR — DB Single OPEN Guarantee`

`OCR — WSS Reorg Correctness`

`OCR — Real Runtime Intelligence Feed`

Yeni R numarası açılmaz.

---

## Status

🟢 CLOSED

## OCR Final Technical Pre-Audit — 2026-08-12

Status: ✅ PASS WITH MINOR HARDENING COMPLETED

Bağımsız adversarial denetim sonrası kalan iki teknik P2 bulgu da
kapatıldı:

- WSS stop timeout sonrası second-stage transport close + task cancel
- gerçek Runner lifecycle E2E kanıtı

Placeholder/container hijyeni:

- boş Dockerfile kaldırıldı
- boş docker-compose.yml kaldırıldı
- generated Python/pytest cache repository kapanışından önce temizlenir
- structural __init__.py ve .gitkeep dosyaları korunur

Final teknik doğrulama:

- full regression: 870 PASS
- closure / soak / E2E: 26 PASS
- DB integrity_check: ok
- DB quick_check: ok
- authority audit: PASS
- diff check: PASS
- WSS shutdown targeted: 27 PASS
- Runner composition-root E2E: PASS
- dependency-owned websockets.legacy warning: NON-BLOCKING

Phase sınırı:

- Phase 11: CLOSED
- Phase 12: RESERVED
- Phase 12 henüz implementation olarak açılmamıştır.

---

## OCR Final Closure Seal — 2026-08-13

Status: ✅ CLOSED

### Final doğrulama

- full regression: 873 PASS
- production-path E2E: PASS
- restart/recovery: PASS
- WSS pair/token membership guard: PASS
- paper schema v3: PASS
- opening-context persistence: PASS
- paper outcome replay: PASS
- DB-level single OPEN invariant: PASS
- DB integrity_check: PASS
- DB quick_check: PASS
- authority boundary: PASS
- learning auto-apply: DISABLED
- independent re-audit: COMPLETE

### Faz sınırı

- Phase 11: CLOSED
- Phase 12: RESERVED
- Phase 12 implementation henüz açılmamıştır
