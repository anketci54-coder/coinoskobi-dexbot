# BINTRBOT — CANONICAL ROADMAP

## ANA AMAÇ

BINTRBOT, Binance TR üzerinde işlem yapmak üzere tasarlanan veri, piyasa zekâsı, araştırma, yapay zekâ, risk ve execution platformudur.

Ana işlem merkezi: **BINANCE TR**

İlk aktif işlem evreni: **TR-MARKET / TRY-CORE**

Temel prensip:

> Önce işe yarayan küçük çekirdeği kanıtla. Daha fazla veri yalnızca ölçülebilir ek katkı sağlıyorsa sisteme dahil et.

---

## 0. CANONICAL MİMARİ

    BINTRBOT
    │
    ├── IDENTITY
    │   ├── ASSET-REGISTRY
    │   ├── MARKET-REGISTRY
    │   └── CONTRACT-REGISTRY
    │
    ├── TR-MARKET
    │   ├── TRY-CORE                  ← AKTİF
    │   ├── USDT-CORE                 ← GELECEK
    │   ├── USDC-CORE                 ← GELECEK
    │   └── OTHER-CORE                ← REZERVE
    │
    ├── DATA
    │   ├── RAW / BRONZE
    │   ├── SILVER
    │   └── GOLD
    │
    ├── TR-MARKET-INTEL
    ├── ASSET-INTEL
    ├── WALLET-INTEL
    ├── CHAIN-INTEL
    ├── DEX-INTEL
    ├── EVENT-INTEL
    ├── GLOBAL-RADAR
    │
    ├── RESEARCH
    │   └── KNOWLEDGE-GRAPH / OBSIDIAN
    │
    ├── BACKTEST-REPLAY
    ├── AI-LAB
    ├── RISK
    ├── EXECUTION
    └── CONTROL

---

## 1. VERİ ZAMANI — BITEMPORAL KURAL

BINTRBOT yalnızca olayın ne zaman gerçekleştiğini değil, sistemin o bilgiyi ne zaman bildiğini de tutar.

Gerçek dünya zamanı:

- EVENT_TIME
- VALID_FROM
- VALID_TO

Sistem / bilgi zamanı:

- OBSERVED_AT
- INGESTED_AT
- KNOWN_AT
- SYSTEM_VALID_FROM
- SYSTEM_VALID_TO

Bir kayıt düzeltildiğinde eski kayıt ezilmez. Yeni sürüm eklenir.

Temel kural:

**KNOWN_AT > SIMULATION_TIME ise bilgi o simülasyonda kullanılamaz.**

---

## 2. İKİ AYRI TARİHSEL ARAŞTIRMA MODU

### RESEARCH MODE

Bugün erişilebilen tarihsel gerçekliği kullanır.

Amaç:
- piyasa davranışını incelemek
- pattern keşfetmek
- hipotez oluşturmak

Soru: **Bugün geriye bakınca ne biliyoruz?**

### POINT-IN-TIME REPLAY MODE

Yalnızca simülasyon tarihinde gerçekten erişilebilir olan bilgiyi kullanır.

Amaç:
- gerçekçi backtest
- walk-forward
- strateji doğrulaması

Soru: **O gün sistem gerçekten ne bilebilirdi?**

Trading performansı değerlendirilirken esas mod: **POINT-IN-TIME REPLAY**

---

## 3. KALICI KİMLİK SİSTEMİ

Ticker/symbol tek başına kimlik değildir.

Ana kimlikler:

- ASSET_ID
- MARKET_ID
- CONTRACT_ID
- CHAIN_ID
- ENTITY_ID
- WALLET_ID
- EVENT_ID
- SOURCE_ID

ASSET_ID ekonomik varlığı; MARKET_ID ise belirli bir işlem piyasasını temsil eder.

---

## 4. CONTRACT MIGRATION KURALI

Contract değişmesi otomatik olarak aynı ASSET_ID anlamına gelmez.

Aynı asset kabulü için:

- resmi migration
- holder conversion
- supply continuity
- project identity continuity
- economic rights continuity
- redemption/swap mechanism
- issuer/project confirmation

değerlendirilir.

Sonuç:
- SAME_ASSET
- NEW_ASSET
- UNCERTAIN

UNCERTAIN durumda eski ve yeni contract otomatik birleştirilmez.

---

## 5. MARKET UNIVERSE — POINT-IN-TIME

Bugünkü aktif market listesi geçmişin market evreni değildir.

Her market için:

- LISTED_AT
- TRADING_STARTED_AT
- TRADING_ENDED_AT
- DELISTED_AT
- STATUS
- KNOWN_AT

tutulur.

Backtest sırasında yalnızca o tarihte gerçekten işlem gören marketler kullanılmalıdır.

Bugünkü aktif marketleri geçmişe taşımak **market survivorship bias** oluşturur.

Delist edilmiş historical marketler erişilebiliyorsa dataset'e alınır. Erişilemiyorsa sınırlama raporlanır.

---

## 6. SNAPSHOT KURALI

308 aktif TRY sembolü gibi bilgiler kalıcı gerçek değil, tarihli snapshot'tır.

Örnek:

- SNAPSHOT_AT = 2026-09-23
- ACTIVE_TRY_MARKETS = 308
- SOURCE = BINANCE_TR

Evren zamanla değişebilir.

---

## 7. SOURCE REGISTRY

Her veri türü alınmadan önce kaynağı değerlendirilir.

Her kaynak için:

- SOURCE_ID
- DATA_TYPE
- PROVIDER
- OFFICIAL / THIRD_PARTY
- HISTORICAL_START
- HISTORICAL_DEPTH
- LIVE_SUPPORT
- RATE_LIMIT
- COST
- AUTH_REQUIRED
- UPDATE_FREQUENCY
- KNOWN_LIMITATIONS
- ALTERNATIVE_SOURCE
- LAST_VALIDATED_AT

Özellikle önceden erişilebilirlik testi yapılacak veriler:

- historical holder count
- historical holder distribution
- historical whale holdings
- historical token supply
- token unlock history
- DEX liquidity history
- wallet labeling

Veri mevcut değilse: **HISTORICAL_DATA_UNAVAILABLE**

---

## 8. RISK — BAŞTAN TASARLANIR

Risk execution aşamasında sonradan eklenmez. FAZ 0'dan itibaren tasarımda bulunur.

Başlangıçta emir vermez.

Tanımlanacak:

- position sizing
- max exposure
- liquidity requirement
- spread ceiling
- slippage ceiling
- daily loss limit
- stop policy
- kill switch
- authority boundaries

Gerçek işlem authority en son açılır.

---

# FAZ 0 — DATA FOUNDATION

**CURRENT PHASE**

Amaç: TRY-CORE için güvenilir temel piyasa datası oluşturmak.

## 0A — Identity + TRY-CORE

- ASSET_ID
- MARKET_ID
- aktif TRY marketleri
- historical market identity
- base asset
- quote asset
- status
- first observed
- last observed

### EXIT GATE 0A

- Mevcut TRY marketlerinin %100'ü kayıtlı
- Duplicate market identity = 0
- Belirsiz eşleşmeler quarantine edilmiş
- Market snapshot timestamp mevcut

## 0B — Historical 1m Klines

Her marketin mevcut historical kapsamı kadar:

- 1m OHLCV
- timestamp
- monthly partition
- Parquet/Zstd
- manifest
- SHA256
- checkpoint

### EXIT GATE 0B

- Hedeflenen market kapsamı işlendi
- Service completion doğrulandı
- Fatal error = 0
- Manifest coverage = %100
- Checksum coverage = %100

## 0C — Live Capture

Canlı:

- aggTrades
- L2 diff-depth
- REST snapshot
- sequence IDs
- source timestamp
- receive timestamp

### EXIT GATE 0C

- en az 7 günlük gözlem
- reconnect testi PASS
- kontrollü sequence-gap injection testi PASS
- gap detection PASS
- resync/recovery PASS
- freshness monitor aktif
- dropped event ölçümü aktif

Doğrudan kanıtlanamayan "algılanmayan gap = 0" kriteri kullanılmaz.

## 0D — Historical aggTrades

Historical aggTrades önemli veri katmanıdır ancak ilk backtest'in otomatik zorunlu şartı değildir.

Veri yeterlilik kapısı **STRATEGY_DEPENDENT** olacaktır.

Trade-flow kullanan strateji için aggTrades gerekir. Sadece OHLCV stratejisi için gerekmez.

Hatta:

- ID pagination
- checkpoint
- duplicate check
- continuity
- chunked Parquet
- SHA256
- manifest

kullanılır.

---

# FAZ 1 — DATA INTEGRITY & OPERATIONS

## 1A — Full Audit

- missing minute
- duplicate
- timestamp disorder
- corrupt file
- impossible OHLC
- invalid volume
- manifest mismatch
- checksum mismatch

Bilinen vaka: **ALGO_TRY / 2023-03**

## 1B — Gap Repair

Kaynak tekrar sorgulanır.

Kaynakta yoksa: **SOURCE_DATA_UNAVAILABLE**

Fake candle yok. Sessiz forward-fill yok.

## 1C — Freshness Monitoring

Servisin yalnızca active olması yeterli değildir.

Her feed için:

- LAST_SOURCE_EVENT
- LAST_RECEIVED_EVENT
- EXPECTED_INTERVAL
- CURRENT_LAG
- STALE_THRESHOLD

izlenir.

SERVICE_ACTIVE=true ama DATA_FRESH=false olabilir. Bu durumda alarm üretilir.

## 1D — Recovery

Test edilecek:

- process crash
- VPS reboot
- partial file
- checkpoint restart
- WebSocket reconnect
- corrupted output quarantine
- backup restore

### EXIT GATE FAZ 1

- unresolved critical corruption = 0
- açıklanamayan critical gap = 0
- recovery test PASS
- freshness alarm PASS
- disk guardian PASS
- backup restore drill PASS

---

# FAZ 2 — DATA LAKE + MVP FEATURES

## 2A — Bronze

- immutable
- provenance
- event time
- known time
- system version
- checksum

## 2B — Silver

- canonical schema
- duplicate removal
- timestamp normalization
- quality flags
- gap flags
- quarantine
- bitemporal fields

## 2C — MVP Timeframes

Başlangıçta:

- 1m
- 5m
- 15m
- 1h
- 4h
- 1d

Yalnızca ihtiyaç çıkarsa diğer timeframe'ler eklenir.

## 2D — Dataset Versioning

Her build:

- DATASET_VERSION
- SCHEMA_VERSION
- INPUT_VERSION
- BUILD_TIME
- CHECKSUM
- PROVENANCE

taşır.

Eski dataset build'leri sessizce ezilmez.

### EXIT GATE FAZ 2

- deterministic build PASS
- reproducibility PASS
- future leakage test PASS
- Silver quality PASS

---

# FAZ 3 — TR MARKET INTELLIGENCE

İlk hipotezi test etmek için gereken minimum piyasa zekâsı.

## 3A — Price / Momentum

- return
- momentum
- volatility
- drawdown
- relative strength

## 3B — Trade Flow

Yalnızca aggTrade verisi strateji için gerekiyorsa:

- aggressive buy
- aggressive sell
- buy/sell ratio
- trade intensity
- large trade
- volume acceleration

## 3C — Liquidity / Order Book

Gerçek L2 mevcut dönemde:

- spread
- depth
- imbalance
- slippage
- liquidity stress

Historical L2 bulunmayan dönemlerde geriye dönük gerçek spread/slippage varmış gibi davranılmaz.

Varsayım kullanılırsa açıkça MODEL_ASSUMPTION olarak raporlanır.

## 3D — TRY Relative Ranking

- return rank
- volume rank
- liquidity rank
- volatility rank
- flow rank

### EXIT GATE FAZ 3

Seçilen baseline stratejinin gerektirdiği minimum feature seti hazır.

---

# CHECKPOINT A — İLK BASELINE KANITI

Burada platform geliştirmeyi durdurup ölçüm yapılır.

Soru:

> Binance TR market datasıyla ücretler ve uygulanabilir execution varsayımları sonrası tekrar edilebilir signal var mı?

Baseline örnekleri:

- buy-and-hold benchmark
- momentum
- relative momentum
- reversal
- volume filter

Her stratejinin kendi DATA_REQUIREMENTS listesi vardır.

Bir stratejinin kullanmadığı veri eksik diye backtest engellenmez.

---

## TRAIN / VALIDATION / TEST KURALI

Aynı test dönemi feature seçmek için tekrar tekrar kullanılamaz.

Zaman bölümü:

- TRAIN
- VALIDATION
- FINAL_TEST

TRAIN model/parametre öğrenimi içindir.

VALIDATION:
- feature seçimi
- threshold seçimi
- model karşılaştırması
- enrichment testi

FINAL_TEST mümkün olduğunca dokunulmamış tutulur.

Final test'e bakılarak yeni feature eklenirse bu dönem artık gerçek final test değildir; yeni untouched dönem gerekir.

---

## EXPERIMENT REGISTRY

Her araştırma denemesi kaydedilir:

- EXPERIMENT_ID
- STARTED_AT
- DATASET_VERSION
- TRAIN_RANGE
- VALIDATION_RANGE
- TEST_RANGE
- FEATURE_SET
- PARAMETERS
- HYPOTHESIS
- RESULT
- DECISION

Amaç test-set overfitting ve bilinçsiz tekrar denemeyi azaltmaktır.

---

# CHECKPOINT A KARARI

Olası durumlar:

- NO_SIGNAL
- SIGNAL_WEAK
- SIGNAL_PROMISING

NO_SIGNAL ise çekirdek hipotez yeniden incelenir.

SIGNAL_WEAK ise ek intelligence katmanları validation üzerinde denenebilir.

SIGNAL_PROMISING ise zorunlu olarak FAZ 4–11 beklenmez.

---

# FAST PATH — PAPER'A KISA YOL

    FAZ 0
      ↓
    FAZ 1
      ↓
    FAZ 2
      ↓
    FAZ 3
      ↓
    CHECKPOINT A
      ↓
    FAZ 12 — Execution-Realistic Backtest / Acceptance Gate
      ↓
    FAZ 13 — Paper Trading

**FAZ 4–11 Paper Trading için zorunlu değildir.**

Wallet, DEX, Obsidian, tokenomics, event intelligence ve AI modelleri beklenmez.

---

# FAZ 4 — ASSET & WALLET PILOT

İlk aşamada tüm marketlerde değil, sınırlı pilot assetlerde.

## 4A — Tokenomics

- circulating supply
- total supply
- max supply
- market cap
- FDV
- unlocks

KNOWN_AT zorunlu.

## 4B — Whale Registry

Her label:

- LABEL
- EVIDENCE
- METHOD
- SOURCE
- CONFIDENCE
- EVALUATED_AT
- KNOWN_AT

taşır.

## 4C — Wallet Graph

Bağlantılar:

- funding
- transfer
- bridge
- contract interaction

Confidence yanında evidence, method, source ve evaluation time zorunludur.

## 4D — Successful Wallet Evaluation

Survivorship bias yasaktır.

Her değerlendirme:

- EVALUATION_START
- EVALUATION_END
- KNOWN_AT
- OBSERVATION_COUNT
- TRADE_COUNT
- DATA_COVERAGE
- FEE_MODEL
- SLIPPAGE_MODEL
- REALIZED_PNL
- UNREALIZED_PNL
- WIN_RATE
- MEDIAN_RETURN
- MAX_DRAWDOWN

taşır.

Bugün başarılı bulunan wallet geçmişte otomatik olarak başarılı sayılmaz.

---

# FAZ 5 — ON-CHAIN & DEX PILOT

Önce pilot assetlerde.

## 5A — Chain Activity
## 5B — Whale Flow
## 5C — DEX Liquidity
## 5D — LP Activity

Kaynak uygunluğu ve maliyet önceden doğrulanır.

---

# FAZ 6 — TOKEN LIFECYCLE

## 6A — ICO / IDO / IEO / TGE / Airdrop
## 6B — İlk DEX/CEX fiyatı
## 6C — Binance Global / Binance TR listing
## 6D — 1h / 6h / 24h / 7d / 30d / 90d davranışı

---

# FAZ 7 — BINANCE TR EVENT INTELLIGENCE

## 7A — Listing / Delisting
## 7B — Event Clock
## 7C — Product Events
## 7D — External Events

Her event:

- EVENT_TIME
- ANNOUNCED_AT
- KNOWN_AT
- SOURCE
- CONFIDENCE

taşır.

Kanıt yoksa: **CAUSE_UNKNOWN**

---

# FAZ 8 — FIAT & GLOBAL RADAR

## 8A — TRY Context
## 8B — Binance Global Radar
## 8C — Lead / Lag
## 8D — Incremental Value Test

Global veri sadece ölçülebilir katkı sağlıyorsa aktif feature olur.

---

# FAZ 9 — KNOWLEDGE GRAPH / OBSIDIAN

İlk stratejinin ön şartı değildir.

Canonical truth: **SQL / Parquet**

Obsidian:
- araştırma
- wallet graph
- event chronology
- analyst notes

içindir.

Akış:

    Canonical DB
       ↓
    Markdown Export
       ↓
    Obsidian

Kontrolsüz ters yazım yapılmaz.

---

# CHECKPOINT B — ENRICHMENT A/B TEST

FAZ 4–8 özellikleri tek tek validation üzerinde sınanır.

    BASE
    BASE + TOKENOMICS
    BASE + WALLET
    BASE + DEX
    BASE + EVENTS
    BASE + GLOBAL

Ölçülecek:

- net expectancy
- drawdown
- stability
- turnover
- execution cost
- incremental contribution

Katkı göstermeyen feature ana modele alınmaz.

Final test feature seçimi için kullanılmaz.

---

# FAZ 10 — GOLD AI DATASET

Sadece faydası doğrulanan veriler.

- point-in-time
- bitemporal
- provenance
- dataset version
- no leakage

---

# FAZ 11 — AI LAB

AI zorunlu değildir.

Baseline yeterliyse Paper AI beklemeden başlayabilir.

AI yalnızca ek katkı sağlayıp sağlamadığı ölçülerek eklenir.

## 11A — Baseline ML
## 11B — Market Model
## 11C — Microstructure Model
## 11D — Gerekirse Event / Wallet Model

---

# FAZ 12 — EXECUTION-REALISTIC BACKTEST / REPLAY

FAZ 12'ye iki yoldan gelinir:

    FAST PATH:
    CHECKPOINT A → FAZ 12

    ENRICHED PATH:
    CHECKPOINT B / AI → FAZ 12

## 12A — Historical Replay
## 12B — Walk Forward

## 12C — Execution Reality

- fee
- spread
- slippage
- latency
- available liquidity

Gerçek historical veri yoksa assumption açıkça etiketlenir.

## 12D — ACCEPTANCE GATE

Paper'a geçmek için önceden tanımlı kriterler gerekir.

Örneğin:

- positive net expectancy
- sufficient sample
- acceptable drawdown
- regime robustness
- cost-after-positive result

---

# FAZ 13 — PAPER TRADING

Baseline veya enriched strateji kullanılabilir.

AI zorunlu değildir.

## 13A — Signal
## 13B — Entry
## 13C — Exit
## 13D — Performance Audit

Backtest ile Paper farkı ayrıca ölçülür.

---

# FAZ 14 — MANUAL ASSISTED

Binance TR API bağlanır.

İnsan onayı gerekir.

- balance
- order
- execution
- audit trail

Secret:
- GitHub'a yazılmaz
- loglanmaz
- dataset'e girmez
- sohbete gönderilmez

---

# FAZ 15 — CONTROLLED AUTO

Yalnızca önceki kapılar PASS ise.

- Risk Gate
- sizing
- automatic execution
- TP/SL
- max exposure
- daily loss
- liquidity limits
- kill switch

---

# FAZ 16 — MARKET EXPANSION

TRY-CORE doğrulandıktan sonra:

    TR-MARKET
    ├── TRY-CORE
    ├── USDT-CORE
    ├── USDC-CORE
    └── OTHER-CORE

Asset intelligence ortak kalır. Market data ayrı tutulur.

---

# L2 HISTORICAL LIMITATION RULE

Gerçek historical L2 mevcut değilse:

- geçmiş gerçek spread uydurulmaz
- order-book reconstruction uydurulmaz
- historical slippage gerçekmiş gibi sunulmaz

Kullanılan tahminler **MODEL_ASSUMPTION** olarak açıkça raporlanır.

Canlı kayıt tarihinden itibaren gerçek L2 evidence kullanılabilir.

---

# WALLET INTELLIGENCE — DEĞİŞMEZ KURALLAR

- Kaynaksız label yok
- Evidence olmadan ilişki yok
- Confidence yanında yöntem zorunlu
- Evaluation date zorunlu
- Survivorship bias yasak
- Unrealized ≠ realized
- Transfer ≠ trade
- Exchange internal movement ≠ market trade
- Cost basis bilinmiyorsa PnL uydurulmaz
- Wallet yalnızca o tarihte bilinebilen bilgiyle değerlendirilir

---

# FAZLARIN ORTAK EXIT-GATE STANDARDI

Bir faz kod yazıldığı için tamamlanmış sayılmaz.

- SCOPE_COMPLETE
- REQUIRED_TESTS_PASS
- REQUIRED_DATA_QUALITY_PASS
- FAILURE_RECOVERY_PASS
- KNOWN_LIMITATIONS_RECORDED
- SOURCE_PROVENANCE_COMPLETE
- NO_UNRESOLVED_CRITICAL_ERROR

Required kapsam stratejiye göre belirlenir.

Kullanılmayan veri katmanının eksik olması ilgili stratejiyi gereksiz yere bloke etmez.

---

# ŞU ANKİ DURUM

Current Phase: **FAZ 0 — DATA FOUNDATION**

Tarihli snapshot: **2026-09-23**

Mevcut gözlenen TRY market sayısı: **308**

Aktif:

- /root/bintrbot
- TRY-CORE current universe
- Historical 1m backfill
- Live aggTrade
- Live L2 diff-depth
- REST depth snapshots
- Parquet/Zstd
- manifest/checksum altyapısı

Historical aggTrades hazırlanmıştır ancak kline backfill süresince durdurulmuştur.

Bu durum ilk yalnızca-kline baseline'ını otomatik olarak bloke etmez.

Bilinen quality case:

**ALGO_TRY / 2023-03 → gap=1**

FAZ 1'de doğrulanacaktır.

---

# CANONICAL EXECUTION ORDER

    FAZ 0   Data Foundation
    FAZ 1   Data Integrity & Operations
    FAZ 2   Data Lake + MVP Features
    FAZ 3   TR Market Intelligence

    CHECKPOINT A
    FIRST BASELINE EVIDENCE

             ┌──────────────────────────────┐
             │                              │
             ▼                              ▼

    FAST PATH                    ENRICHMENT PATH

    FAZ 12                       FAZ 4  Asset/Wallet Pilot
    Acceptance Gate              FAZ 5  On-chain/DEX
             │                  FAZ 6  Token Lifecycle
             ▼                  FAZ 7  Event Intel
    FAZ 13 Paper                 FAZ 8  Fiat/Global
                                 FAZ 9  Obsidian
                                 CHECKPOINT B
                                 FAZ 10 Gold
                                 FAZ 11 AI
                                      │
                                      ▼
                                 FAZ 12
                                      │
                                      ▼
                                 FAZ 13 Paper

    FAZ 14 Manual Assisted
    FAZ 15 Controlled Auto
    FAZ 16 Market Expansion

---

# SCOPE FREEZE

Bu roadmap sürümünden sonra ilk baseline öncesinde yeni ana modül eklenmez.

Aktif odak:

- FAZ 0
- FAZ 1
- FAZ 2
- FAZ 3
- CHECKPOINT A

Yeni fikirler **BACKLOG** olarak kaydedilir.

İlk baseline kanıtını geciktirmez.

---

# CANONICAL PRINCIPLE

**Önce kalıcı kimlik.  
Önce doğru zaman.  
Önce historical universe.  
Önce gerçek veri.  
Sonra veri bütünlüğü.  
Sonra küçük ve test edilebilir hipotez.  
Sonra ilk baseline.  
Başarılı baseline varsa Paper'a kısa yol açık.  
Zenginleştirme yalnızca ölçülen katkıyla eklenir.  
Risk baştan tasarlanır.  
Execution en son açılır.**

İlk aktif işlem evreni:

**TR-MARKET / TRY-CORE**
