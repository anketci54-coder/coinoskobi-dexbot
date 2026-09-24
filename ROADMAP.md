# COINOSKOBI DEXBOT — CANONICAL ROADMAP

<!-- CANONICAL_CURRENT_STATE_20260924 -->
## Canonical roadmap status note — 2026-09-24

Reference commit: `72c71a04632556c596493ba9fecb17a60e2ecbd2`.

Current runtime policy is USDT-only for universe observation, hot-path candidate routing, panel universe projection and PAPER entry admission. This is an operating policy, not a permanent architectural capability limit.

### Phase-state interpretation

- Architectural phase closure and later maintenance are separate.
- Later fixes do not automatically reopen a CLOSED phase.
- Historical acceptance records remain evidence; they are not fresh runtime verification.
- Missing historical subphase details must not be invented.

### Phase 15H documentation reconciliation

A 2026-09-23 Phase 15H acceptance seal exists. Any older `OPEN / DESIGN+IMPLEMENTATION PENDING` wording is historical and does not describe the current phase state.

The acceptance seal does **not** prove that every original design sentence was implemented literally. In particular, current `app/execution/paper_simulation.py` starts the local Anvil fork from a configured RPC URL; therefore documentation must not claim that the fork transport itself is routed through the Phase 8 broker. Phase 8 remains the owner of provider/resilience policy, while 15H owns the non-broadcast simulation sandbox/evidence boundary.

Likewise, 15H documentation must distinguish fields/contracts from evidence actually measured by the simulator. Unsupported or unmeasured execution properties remain `UNKNOWN`; an accepted phase does not convert them into measured facts.


Bu dosya Coinoskobi'nin tek resmi mimari ve geliştirme sınıflandırmasıdır.

## MİMARİ ANAYASA

- Ana mimari yalnız **PHASE 0–15**'tir.
- PHASE 16, ERA, architecture V2/V3 veya eşdeğer paralel roadmap zinciri açılmaz.
- PancakeSwap V2/V3 adları yalnız gerçek DEX protokol sürümünü ifade eder.
- Yeni iş önce mevcut Phase 0–15 sahibine atanır.
- Mevcut alt faz sahipliği işi karşılıyorsa o alt faz güncellenir; aynı kapsam için yeni alt faz açılmaz.
- Mevcut alt fazlara sığmayan ayrı ve kalıcı sahiplik gerekiyorsa yalnız aynı ana Phase altında sıradaki kullanılmamış düz harf açılabilir.
- Küçük bug fix, provider ayarı, test, refactor, isim değişikliği veya panel düzeltmesi için yeni faz/alt faz açılmaz.
- Mevcut alt faz adları düz harflerle kalır; 12B1/12B2A gibi iç içe numaralandırma kullanılmaz.
- Geçici probe, disposable script, deney collector'ı veya ayrı araştırma roadmap'i kalıcı mimariye eklenmez.
- BSC başlangıç ağıdır; network/DEX için ayrı pipeline kopyalanmaz.
- Token identity chain-aware, pool identity chain+dex+pool olmalıdır.
- Observation, decision, paper, wallet, signing ve execution authority birbirinden ayrıdır.
- Hard safety matematiksel skordan üstündür. Missing/UNKNOWN evidence güvenli kabul edilmez.
- Hot path pahalı RPC, AI, history scan veya ağır DB aggregate beklemez.
- Ağır işler bounded worker/slow-path üzerinde çalışır; queue/cache/readmodel yapıları bounded kalır.
- Provider kapasitesi sınırsız kabul edilmez; quota/rate-limit/backpressure mimari girdidir.
- Private key, seed phrase veya provider secret repository/log/status çıktısına yazılmaz.
- Gereksiz mikroservis, Kafka, Celery, Redis veya paralel runtime kurulmaz.
- Kalıcı değişiklikler targeted test + smoke/E2E + gerektiğinde full regression + post-audit ile kapanır.

## ALT FAZ YÖNETİM PROTOKOLÜ

Bu protokol Phase 0–15 iskeletinin bozulmadan genişletilmesi için bağlayıcıdır:

1. Her yeni bakım/geliştirme işi önce mevcut **Phase 0–15** ana sahibine atanır.
2. İlgili ana Phase'in mevcut canonical alt fazları düz harf sırasıyla (`A/B/C/D...`) incelenir.
3. İş mevcut alt fazın amacı/sahipliği içinde kalıyorsa **o alt faz güncellenir veya değiştirilir**; yeni alt faz açılmaz.
4. İş mevcut alt fazların hiçbirine sığmayan, ayrı ve kalıcı bir sahiplik gerektiriyorsa yalnız aynı ana Phase altında **sıradaki kullanılmamış düz harf** açılabilir.
5. Yeni alt faz ancak gerçek sahiplik ayrımı için açılır; küçük bug fix, provider ayarı, test, refactor, isim değişikliği, UI/panel düzeltmesi veya tekil runtime repair için açılmaz.
6. `14B1`, `12B2A` gibi nested numaralandırma; Phase 16; ERA; architecture V2/V3; OCR/R-number; post-roadmap veya paralel roadmap yasaktır.
7. Yeni modül/script/service/provider/router/pipeline oluşturmadan önce repository-wide existing implementation ve reference audit yapılır. Aynı işi yapan ikinci canonical yol kurulmaz; mevcut parça genişletilir, değiştirilir veya yerini yeni parça alıyorsa eski parça kaldırılır.
8. Kullanılmayan, duplicate, superseded, debug/disposable veya artık referanslanmayan executable script/modül/config/test-helper dosyaları reference audit + targeted/full test kanıtından sonra silinir. Dead executable code "belki lazım olur" gerekçesiyle tutulmaz.
9. Tarihsel phase-scoped raporlar, closure kayıtları ve audit evidence belgeleri kanıt olarak tutulabilir; bunlar aktif mimari veya executable sahiplik oluşturmaz.
10. Her değişiklik canonical data flow, authority ayrımı, fail-closed güvenlik, DB/runtime sahipliği ve bounded çalışma kurallarını korur. Maintenance işi mimari mutasyon yaratamaz.
11. Kapanış sırası: mevcut sahipliği doğrula → targeted implementation → targeted tests → canonical smoke/E2E → gerekiyorsa full regression → compile/DB integrity/post-audit → GitHub → VPS clean-state/sync → runtime acceptance.
12. Yeni sohbet/AI/agent oturumu bu sınıflandırmayı tahmin ederek değil, önce canonical dokümanları okuyarak uygular.

## PROJE DURUMU

PHASE 0–15 tamamlanmıştır. Sistem bakım/doğrulama dönemindedir; her bakım işi yine aşağıdaki mevcut fazlardan birinin sahipliğinde yürütülür.

- Phase 0–14: CLOSED
- Phase 15: CLOSED — FINAL ROADMAP PHASE

---

# PHASE 0 — Critical Bug Fixes

Amaç: botu temel olarak çalışır, temiz ve test edilebilir tutmak.

Sahiplik:
- erken kritik bug fixleri
- temel dependency/requirements temizliği
- duplicate/kullanılmayan temel kodların kaldırılması
- geçici script ve debug kalıntılarının temizliği

Durum: CLOSED.

---

# PHASE 1 — Core Infrastructure

Amaç: kalıcı çekirdek ve veri bütünlüğü.

Sahiplik:
- runner/logger/config/composition altyapısı
- SQLite WAL, schema/migration, transaction/recovery
- DB-level invariants ve concurrency
- dependency reproducibility ve lifecycle

Durum: CLOSED.

---

# PHASE 2 — Performance & Scalable Pipeline Core

Amaç: bounded, chain-aware ortak candidate/universe altyapısı.

Sahiplik:
- ingress gate ve bounded candidate admission
- dedup/cooldown/priority/fairness
- analyzer cache ve common Candidate modeli
- network/DEX/source adapter registry
- durable UniverseRegistry
- PancakeSwap V2/V3 discovery ve checkpointing
- dynamic universe ve bounded scheduler/readmodels

Full-universe adıyla ayrı roadmap yoktur.

Durum: CLOSED.

---

# PHASE 3 — Risk, Opportunity & Entry Feasibility

Amaç: girişin güvenlik ve ekonomik fizibilitesini deterministik evidence ile değerlendirmek.

Sahiplik:
- sellability/honeypot/tax evidence
- bytecode/rug/trap ve MEV exposure
- execution cost ve entry feasibility
- unified score/decision
- hard-risk separation
- conservative paper admission

Kurallar: confirmed danger veto üretebilir; UNKNOWN safe değildir; Phase 3 live/wallet/signing authority taşımaz.

Durum: CLOSED.

---

# PHASE 4 — Position Lifecycle

Amaç: açılmış pozisyonun deterministik mekanik yönetimi.

Sahiplik:
- TP1/TP2/TP3 + runner allocation
- deterministic state machine
- fraction conservation
- monotonic protective/trailing stop
- lifecycle recovery

Durum: CLOSED.

---

# PHASE 5 — DEX Market Intelligence

Amaç: DEX piyasasındaki gerçek kısa-horizon durumu bounded kaynaklardan gözlemlemek.

Sahiplik:
- price/liquidity/volume/txns/participation evidence
- native Swap/Sync/Mint/Burn context
- flow/reserve/price-impact/market-quality
- DexScreener bounded snapshots ve display metadata
- runtime market-flow producer zinciri

DexScreener identity kaynağı değildir; provider failure safe evidence değildir.

Durum: CLOSED.

---

# PHASE 6 — DEX Exit Intelligence

Amaç: trend sağlığı, exhaustion, divergence, runner health ve protective exit bağlamı.

Canonical alt fazlar: 6A–6J.

Kurallar: persistence/debounce gerekir; adaptive trailing korunan stopu gevşetemez; advisory intelligence live execution emri değildir.

Durum: CLOSED.

---

# PHASE 7 — Flow Confirmation & Market Regime Intelligence

Amaç: fiyat hareketinin gerçek ve sürdürülebilir akışla teyidini ölçmek.

Canonical alt fazlar: 7A–7J.

Sahiplik:
- flow spread/velocity/acceleration
- confirmation/divergence/convergence
- regime classification
- COLD/WARM/HOT seismic market state
- universe observation cadence/priority

COLD/WARM/HOT analyzer-cache terminolojisi değildir.

Durum: CLOSED.

---

# PHASE 8 — Native Event Ingestion & Provider Resilience

Amaç: on-chain RPC/WSS ve native DEX event erişimini sürekli, bounded, quota-aware ve correctness-preserving biçimde taşımak.

Canonical alt fazlar: 8A–8J.

Sahiplik:
- BSC WSS subscription ve application-owned lifecycle
- reconnect/backoff ve event correctness
- duplicate suppression, reorg/retraction, callback-before-ack
- bounded buffers/backpressure
- provider failure classification
- **tek canonical provider broker**
- en fazla dört explicit RPC/WSS provider slotu
- rate-limit/quota/403 circuit-breaker ve cooldown
- transient transport cooldown
- all-circuits-open fail-fast
- heavy RPC methodlarının sağlıklı provider'lar arasında bounded dağıtımı
- exact-request kısa cache ve in-flight coalescing
- bounded primary-first WSS fallback
- worker-owned Web3/provider isolation

Canonical sınır:
- `app/chains/bsc.py` composition/root binding
- `app/dex/provider_broker.py` broker mekanizması
- `app/dex/provider_resilience.py` failure policy
- `app/dex/wss_service.py` WSS application lifecycle

Eski paralel HTTP/WSS failover sınıfları veya ayrı provider mimarileri korunmaz.

Provider broker observation/transport katmanıdır; decision, paper, wallet, signing ve execution authority = false.

Durum: CLOSED.

---

# PHASE 9 — Wallet / Entity / Smart-Money Intelligence

Amaç: native akıştan gerçek wallet/entity davranışı ve participation kalitesi üretmek.

Canonical alt fazlar: 9A–9J.

Sahiplik:
- chain-aware wallet evidence
- transaction.from-only actor identity
- wallet behavior features
- conservative entity linking
- known-wallet provenance
- whale flow ve wallet reputation
- bounded wallet/entity readmodels

Tek whale geniş piyasa katılımı sayılmaz; label trade permission değildir.

Durum: CLOSED.

---

# PHASE 10 — Adversary / Scam-Actor / MEV Intelligence

Amaç: normal katılım ile adversarial davranışı evidence tabanlı ayırmak.

Canonical alt fazlar: 10A–10J.

Sahiplik: MEV/sandwich, scam/rug, wash/sybil, sniper/pump-dump, adversary reputation ve false-positive controls.

Suspicion proof değildir; adversary label trade signal değildir.

Durum: CLOSED.

---

# PHASE 11 — Learning / Calibration / Outcome Memory

Amaç: geçmiş deterministik kararların doğruluğunu ölçmek ve yalnız proposal üretmek.

Canonical alt fazlar: 11A–11J.

Sahiplik:
- outcome evidence/classification
- signal attribution
- false-positive/false-negative memory
- avoided-loss/missed-opportunity/exit-failure memory
- calibration statistics ve proposal layer
- bounded learning readmodel

Proposal apply değildir; auto-threshold/config/source-code değişikliği yoktur.

Durum: CLOSED.

---

# PHASE 12 — Operational Paper-Trade Readiness

Amaç: gerçek application lifecycle içinde discovery'den paper OPEN/CLOSE ve learning feed'e kadar operasyonel zinciri doğrulamak.

Canonical alt fazlar:
- 12A — Paper Readiness Preflight
- 12B — Real Runtime Paper Smoke
- 12C — Paper Operation Start

Sahiplik:
- production composition root
- WSS/market-flow/paper lifecycle binding
- scanner → queue → analysis → intelligence → risk → decision → paper admission
- application-owned systemd runtime
- restart/recovery ve DB health
- cross-phase bounded runtime soak
- **provider operability ve quota/cost budget**
- true composition-root E2E

Phase 12 provider broker'ı yeniden tanımlamaz; Phase 8'deki broker'ın gerçek runtime operability'sini doğrular.

Durum: CLOSED.

---

# PHASE 13 — Paper Outcome Learning & Calibration

Amaç: gerçek paper ve counterfactual outcome evidence ile fırsat kaçırma/kötü işlem dengesini ölçmek.

Canonical alt fazlar:
- 13A — Entry-Time Signal Attribution & Exit Drift Baseline
- 13B — Outcome Segmentation & Calibration Baseline
- 13C — Bounded Counterfactual Observation
- 13D — Unified Outcome Calibration Readmodel

Sahiplik:
- PAPER_CLOSE / COUNTERFACTUAL provenance ayrımı
- false-negative / missed-opportunity / avoided-loss ölçümü
- horizon/follow-up data integrity
- proposal-only calibration
- provider pressure altında bounded counterfactual observation

Canonical pressure kuralı: bir scanner refresh'te pending counterfactual Gecko fetch'i en fazla **30 pool / 1 multi-pool request** tüketir; kalan gözlemler sonraki normal refresh'e bırakılır.

Durum: CLOSED.

---

# PHASE 14 — Command Center & AI Analyst

Amaç: operatöre gerçek runtime truth üzerinden karar desteği vermek.

Sahiplik:
- tek canonical panel `app.api.panel:app`, port 8098
- candidate/universe radar
- paper ledger/accounting/health/intelligence readmodels
- readable token/pool display metadata
- AI açıklama/özet/proposal
- panel read-only authority sınırı

UI değişikliği strategy, DB, paper, wallet, signing veya live execution authority vermez.

Durum: CLOSED.

---

# PHASE 15 — Final Operational Validation & Controlled Micro-Live

Amaç: paper varsayımları ile gerçek execution koşulları arasındaki farkı ölçmek ve yalnız açık kullanıcı onayıyla kontrollü micro-live sınırını yönetmek.

Canonical alt fazlar:
- 15A — Simulation Drift Validator
- 15B — Execution Evidence Adapter
- 15C — Drift Composition
- 15D — Runtime Observation Binding
- 15E — Command Center Drift Projection
- 15F — Deterministic Drift Classification
- 15G — Drift No-Block / Authority Safety Boundary
- 15H — Execution-Grade Paper Simulation

Sahiplik:
- simulation drift
- signal-to-block latency/time drift
- gas/slippage/fill/quote-delay evidence
- paper vs real execution drift
- kill-switch ve explicit approval boundary

### 15H — Execution-Grade Paper Simulation

Amaç: gerçek fon, gerçek order, private key veya signing kullanmadan; explicit block identity üzerinden canonical BSC/Pancake state'inde transaction-level PAPER BUY/SELL execution simülasyonu üretmek.

15H yalnız simulation evidence üretir. Canonical çıktı, mevcut Phase 15B execution-evidence adapter'ına beslenir; 15A/15C/15F drift zinciri bu evidence'ı karşılaştırır/sınıflandırır.

15H sahipliği:
- explicit block / state-snapshot tabanlı deterministic execution sandbox
- canonical Pancake route üzerinde unsigned/synthetic PAPER BUY denemesi
- simulated BUY sonucu: implementationın gerçekten ürettiği success/revert, received-token amount ve gas/receipt evidence; fee/slippage/fill gibi alanlar yalnız ölçülüyorsa FACT, aksi halde UNKNOWN
- mevcut lifecycle tarafından talep edilen zamanda unsigned/synthetic PAPER SELL denemesi
- simulated SELL sonucu: implementationın gerçekten ürettiği success/revert, received-quote amount ve gas/receipt evidence; fee/slippage/fill gibi alanlar yalnız ölçülüyorsa FACT, aksi halde UNKNOWN
- BUY ve SELL simulation evidence/provenance; gerçek BUY→SELL state continuity yalnız implementation bunu aynı mutable fork state üzerinde kanıtlıyorsa FACT sayılır, aksi halde UNKNOWN
- provider cevaplarından bağımsız olarak, simulation'ın gerçekten kanıtladığı execution sonucu; missing/unsupported sonuç UNKNOWN kalır

15H sahip değildir ve devralmaz:
- Phase 3: sellability/honeypot/rug/tax kararı, Risk Gate, entry feasibility, paper admission
- Phase 4/6: TP/SL/runner tetikleme, position lifecycle veya exit-policy kararı
- Phase 8: RPC/WSS provider broker, transport, retry, quota, cooldown veya provider resilience
- Phase 10: MEV/sandwich/adversary detection, attribution veya classification
- Phase 11/13: learning, calibration, outcome memory veya proposal üretimi
- Phase 12: systemd/runtime ownership, scanner/pipeline orchestration, PAPER DB lifecycle veya operational E2E ownership
- Phase 14: panel/Vezir/operator UI veya karar desteği
- Phase 15A–15G: drift comparison, evidence adaptation, composition, classification, projection veya authority-boundary logic

15H authority sınırı:
- transaction broadcast = false
- private key / seed = forbidden
- real wallet use = false
- signing = false
- live order/create = false
- live execution authority = false
- wallet/signing authority = false
- paper admission authority = false
- Risk Gate / hard-block override authority = false
- PAPER position OPEN/CLOSE kararı ve DB mutation 15H'nin görevi değildir

Canonical entegrasyon kuralı:
- Phase 8 canonical provider/resilience ownership korunur. Current 15H implementation local Anvil forkunu configured RPC URL üzerinden başlatır; bu fork bootstrap yolu broker-routed olarak belgelenmez. Ayrı bir genel-purpose provider/resilience mimarisi 15H altında kurulmaz.
- Phase 4/12 mevcut lifecycle/runtime, gerektiğinde 15H'den simulation evidence talep eder; 15H lifecycle sahibi olmaz.
- Phase 3, 15H evidence'ını yalnız kendi mevcut risk/sellability kuralları içinde yorumlayabilir; 15H kendi başına SELLABILITY_OK veya trade permission vermez.
- Phase 10 MEV evidence üretir; 15H MEV detector kopyalamaz.
- Phase 15B, 15H çıktısını canonical execution evidence'a bağlayan tek adapter sınırı olarak kalır.
- Aynı işi yapan ikinci PAPER engine, ikinci strategy engine, ikinci lifecycle veya ikinci provider pipeline oluşturulmaz.

Phase 15 kapanışı live/wallet/signing authority'yi otomatik açmaz.

Durum: CLOSED — FINAL ROADMAP PHASE.
Maintenance sahipliği: **15H OPEN — Execution-Grade Paper Simulation**. Bu, Phase 15'i veya Phase 0–15 mimarisini yeniden açmaz; kapalı roadmap altında kontrollü maintenance genişlemesidir.

---

## BAKIM SINIFLANDIRMA KURALI

Phase 15 sonrasında çıkan her bug/iyileştirme/bakım işi önce Phase 0–15 sahipliğine atanır. Ayrı post-roadmap/provider/universe/experiment mimarisi açılmaz.

Örnek sahiplik:
- provider broker / RPC/WSS resilience → Phase 8
- provider runtime operability / quota budget → Phase 12
- counterfactual provider pressure → Phase 13
- successful-wallet / whale intelligence → Phase 9
- news/market intelligence → mevcut Phase 5/7 kapsamı
- Vezir/AI operator support → Phase 14
- security/adversary evidence → Phase 3/10; core infrastructure security → Phase 1
- transaction-level execution-grade PAPER simulation → Phase 15H

## CANONICAL DOCUMENTS

- `README.md` — proje özeti ve kalıcı kurallar
- `ROADMAP.md` — tek Phase 0–15 sahiplik haritası
- `PROJECT_STATE.md` — güncel operasyonel checkpoint
- `TEST_RESULTS.md` — tarihsel doğrulama kanıtları

Tarihsel phase-scoped raporlar audit evidence olarak kalabilir; aktif roadmap değildir.
