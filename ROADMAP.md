# COINOSKOBI DEXBOT — CANONICAL ROADMAP

Bu dosya Coinoskobi'nin tek resmi mimari ve geliştirme sınıflandırmasıdır.

## MİMARİ ANAYASA

- Ana mimari yalnız PHASE 0–15'tir.
- PHASE 16, ERA, V2/V3 veya eşdeğer paralel roadmap zinciri açılmaz.
- Yeni iş önce mevcut PHASE'e, sonra mevcut alt faza yerleştirilir.
- Alt fazlar düz harflerle adlandırılır: 12A, 12B, 12C gibi.
- Küçük bug fix, provider ayarı, test, refactor, isim değişikliği veya panel düzeltmesi için yeni alt harf açılmaz.
- Yeni alt harf ancak mevcut alt fazların hiçbirine temiz biçimde sığmayan, bağımsız kapsamı ve ölçülebilir kabul kriteri olan gerçek bir ihtiyaçta açılabilir.
- 12B1, 12B2A gibi iç içe numaralandırma kullanılmaz.
- Geçici probe, disposable script, deney collector'ı veya ayrı araştırma roadmap'i kalıcı mimariye eklenmez.
- Git geçmişi tarihsel kanıttır; eski OCR/R/experiment/post-roadmap isimleri aktif mimari sınıfı değildir.
- BSC başlangıç ağıdır. Network veya DEX için ayrı pipeline kopyalanmaz.
- Token identity chain-aware, pool identity chain+dex+pool olmalıdır.
- Observation, decision, paper, wallet, signing ve execution authority birbirinden ayrıdır.
- Hard safety matematiksel skordan üstündür. Missing/UNKNOWN evidence güvenli kabul edilmez.
- Hot path pahalı RPC, AI, history scan veya ağır DB aggregate beklemez.
- Ağır işler bounded worker/slow-path üzerinde çalışır; queue/cache/readmodel yapıları bounded kalır.
- Private key, seed phrase veya secret repository'ye yazılmaz.
- Gereksiz mikroservis, Kafka, Celery, Redis veya paralel runtime kurulmaz.
- Kalıcı değişiklikler targeted test + smoke/E2E + gerektiğinde full regression + post-audit ile kapanır.

## PROJE DURUMU

PHASE 0–15 tamamlanmıştır. Sistem bakım ve doğrulama dönemindedir; fakat her bakım işi yine aşağıdaki mevcut fazlardan birinin sahipliğinde yürütülür.

- Phase 0: CLOSED
- Phase 1: CLOSED
- Phase 2: CLOSED
- Phase 3: CLOSED
- Phase 4: CLOSED
- Phase 5: CLOSED
- Phase 6: CLOSED
- Phase 7: CLOSED
- Phase 8: CLOSED
- Phase 9: CLOSED
- Phase 10: CLOSED
- Phase 11: CLOSED
- Phase 12: CLOSED
- Phase 13: CLOSED
- Phase 14: CLOSED
- Phase 15: CLOSED — FINAL ROADMAP PHASE

---

# PHASE 0 — Critical Bug Fixes

Amaç: botu temel olarak çalışır, temiz ve test edilebilir hale getirmek.

Canonical sahiplik:
- ilk scanner/cache uyumluluk düzeltmeleri
- Gecko pool cache price desteği
- dependency/requirements temizliği
- duplicate ve kullanılmayan temel kodların kaldırılması
- erken kritik bug fixleri

Kural: geçici scriptler kalıcı mimari sayılmaz.

Durum: CLOSED.

---

# PHASE 1 — Core Infrastructure

Amaç: uygulamanın kalıcı çekirdeğini ve veri bütünlüğünü kurmak.

Canonical sahiplik:
- Runner/logger/config/composition temel altyapısı
- paper database ve SQLite WAL
- schema versioning ve ordered migration
- DB-level single OPEN invariant
- SQLite concurrency / transaction / rollback güvenliği
- clean-start, reopen, integrity ve recovery davranışı
- dependency reproducibility ve core lifecycle

Eski OCR/R isimleri altında yapılmış DB schema, concurrency, migration ve recovery işleri artık Phase 1 sahipliğindedir.

Durum: CLOSED.

---

# PHASE 2 — Performance & Scalable Pipeline Core

Amaç: bounded, chain-aware ve ölçeklenebilir ortak candidate/universe altyapısı.

Canonical sahiplik:
- lightweight ingress gate
- bounded candidate admission queue
- deduplication, cooldown, priority ve heap compaction
- AnalyzerCache ve cache reuse
- WARM/PARTIAL/COLD analyzer-cache davranışı
- common Candidate modeli
- network/DEX/source adapter registry
- bounded scheduler ve fairness
- one durable UniverseRegistry
- PancakeSwap V2/V3 pool identity discovery
- EXISTING backfill + NEW tail checkpointing
- dynamic universe; yaş/liquidity nedeniyle registry'den silmeme
- tek cache DB ve tek canonical universe runtime
- queue/scheduler/readmodel boundedness ve soak kanıtları

Full-universe adıyla ayrı roadmap yoktur; registry/discovery/bounded orchestration Phase 2 kapsamıdır.

Durum: CLOSED.

---

# PHASE 3 — Risk, Opportunity & Entry Feasibility

Amaç: bir adaya girmenin güvenli ve ekonomik olarak mantıklı olup olmadığını deterministik evidence ile değerlendirmek.

Canonical sahiplik:
- sellability / honeypot / transfer-tax evidence
- bytecode/rug/trap riskleri
- MEV exposure
- execution cost ve entry feasibility
- unified score / unified decision
- hard-risk separation
- conservative paper admission
- deep sellability yalnız qualified bounded adaylarda

Kurallar:
- confirmed danger hard-block olabilir
- suspicion veya UNKNOWN otomatik güvenli değildir
- hard safety score tarafından override edilemez
- Phase 3 live/wallet/signing authority taşımaz

Durum: CLOSED.

---

# PHASE 4 — Position Lifecycle

Amaç: açılmış pozisyonun deterministik mekanik yönetimi.

Canonical sahiplik:
- TP1/TP2/TP3 + runner allocation
- OPEN → TP1_DONE → TP2_DONE → TP3_DONE → RUNNER_ACTIVE → CLOSED state machine
- fraction conservation
- monotonic protective/trailing stop
- duplicate TP ve TP atlama koruması
- position lifecycle recovery

Ana invariant: yeni protective stop önceki korunan stop seviyesini düşüremez.

Durum: CLOSED.

---

# PHASE 5 — DEX Market Intelligence

Amaç: DEX piyasasında kısa horizonlarda gerçekte ne olduğunu gerçek kaynaklardan gözlemlemek.

Canonical sahiplik:
- bounded real market snapshots
- price, liquidity, volume, txns, participation, FDV/market-cap facts
- PancakeSwap native Swap/Sync/Mint/Burn context
- wall/block/swap clocks
- swap flow, flow acceleration, reserve dynamics, price impact ve market quality
- DexScreener bounded snapshot adapter
- DexScreener baseToken/quoteToken symbol+name metadata'sının kaybolmadan taşınması
- runtime market-flow producer zinciri
- provider failure'ın evidence yokluğu olarak yorumlanmaması

Full-universe market snapshot ve token display metadata üretimi Phase 5 kapsamındadır. DexScreener universe identity kaynağı değildir; market snapshot kaynağıdır.

Durum: CLOSED.

---

# PHASE 6 — DEX Exit Intelligence

Amaç: pozisyon sırasında trend sağlığını ve runner çıkış bağlamını değerlendirmek.

Canonical alt fazlar: 6A–6J.

Canonical sahiplik:
- trend health
- momentum exhaustion
- divergence / exit pressure
- runner health
- adaptive trailing recommendation
- hard-risk / exit context
- hybrid exit controller/runtime binding
- paper exit davranışı ve protection tightening

Kurallar:
- tek kötü tick doğrudan BREAK değildir
- persistence/debounce gerekir
- adaptive trailing korunan stopu gevşetemez
- exit intelligence advisory bağlamdır; live execution emri değildir

Durum: CLOSED.

---

# PHASE 7 — Flow Confirmation & Market Regime Intelligence

Amaç: fiyat hareketinin gerçek, sürdürülebilir ve çoklu piyasa akışıyla teyit edilip edilmediğini ölçmek.

Canonical alt fazlar: 7A–7J.

Canonical sahiplik:
- flow spread, velocity, acceleration
- CONFIRMED/PARTIAL/UNCONFIRMED/CONFLICT/UNKNOWN
- divergence/convergence
- multi-actor flow quality
- persistence/debounce/noise control
- TRENDING_BULL/TRENDING_BEAR/CHOP/CONFLICT/TRANSITION/UNKNOWN regime
- COLD/WARM/HOT seismic market-state classification ve priority semantics
- universe observation cadence/state transition davranışı

COLD/WARM/HOT yalnız market seismic state anlamındadır; analyzer-cache terminolojisi değildir.

Durum: CLOSED.

---

# PHASE 8 — Native Event Ingestion & Provider Resilience

Amaç: native DEX eventlerini sürekli, bounded ve correctness-preserving biçimde taşımak.

Canonical alt fazlar: 8A–8J.

Canonical sahiplik:
- BSC WSS subscription adapter
- application-owned WSS lifecycle
- reconnect/backoff/failover
- subscription health
- duplicate suppression
- transactionHash+logIndex event identity
- removed/reorg RETRACTION semantics
- callback-before-ack delivery correctness
- bounded buffers/backpressure
- provider capability/failure classification
- bounded V2 native bootstrap/deep observation
- worker-owned provider/SQLite isolation

Eski universe-shadow veya OCR WSS repair isimleri ayrı mimari değildir; bu davranışlar Phase 8'e aittir.

Durum: CLOSED.

---

# PHASE 9 — Wallet / Entity / Smart-Money Intelligence

Amaç: native akıştan gerçek wallet/entity davranışı ve participation kalitesi üretmek.

Canonical alt fazlar: 9A–9J.

Canonical sahiplik:
- chain-aware wallet evidence
- transaction.from-only runtime actor identity
- wallet behavior features
- conservative entity linking
- known-wallet provenance
- whale flow
- wallet reputation
- bounded wallet/entity readmodels
- no hindsight identity reconstruction

Tek whale geniş piyasa katılımı sayılmaz; label trade permission değildir.

Durum: CLOSED.

---

# PHASE 10 — Adversary / Scam-Actor / MEV Intelligence

Amaç: normal katılım ile adversarial davranışı evidence tabanlı ayırmak.

Canonical alt fazlar: 10A–10J.

Canonical sahiplik:
- MEV/sandwich evidence
- scam/rug actor patterns
- wash/sybil coordination evidence
- sniper/pump-dump context
- adversary reputation
- wallet/entity/market risk bridge
- bounded adversary readmodel
- false-positive controls

Suspicion proof değildir; adversary label trade signal değildir.

Durum: CLOSED.

---

# PHASE 11 — Learning / Calibration / Outcome Memory

Amaç: geçmiş deterministik kararların doğruluğunu ölçmek ve yalnız proposal üretmek.

Canonical alt fazlar: 11A–11J.

Canonical sahiplik:
- outcome evidence/classification
- signal attribution
- false-positive/false-negative memory
- avoided-loss/missed-opportunity/exit-failure memory
- calibration statistics
- threshold/weight proposal layer
- evidence windows/decay
- bounded learning readmodel
- runtime paper outcome feed

Proposal apply değildir. Auto-threshold/weight/config/source-code değişikliği yoktur.

Durum: CLOSED.

---

# PHASE 12 — Operational Paper-Trade Readiness

Amaç: gerçek application lifecycle içinde discovery'den paper OPEN/CLOSE ve learning feed'e kadar operasyonel zinciri doğrulamak.

Canonical alt fazlar:
- 12A — Paper Readiness Preflight
- 12B — Real Runtime Paper Smoke
- 12C — Paper Operation Start

Canonical sahiplik:
- production composition root
- WSS/market-flow/paper lifecycle binding
- scanner → queue → analysis → intelligence → risk → decision → paper admission zinciri
- real paper OPEN/CLOSE
- application-owned systemd runtime
- restart/recovery
- schema reopen/health
- close idempotency ve outcome replay
- cross-phase bounded runtime soak
- provider/cost budget ve operability
- true composition-root E2E

Eski OCR close/restart/runtime-repair testleri ayrı workstream değildir; Phase 12 operasyon doğrulamasına aittir.

Durum: CLOSED.

---

# PHASE 13 — Paper Outcome Learning & Calibration

Amaç: gerçek paper ve counterfactual outcome evidence ile fırsat kaçırma/kötü işlem dengesini ölçmek.

Canonical alt fazlar:
- 13A — Entry-Time Signal Attribution & Exit Drift Baseline
- 13B — Outcome Segmentation & Calibration Baseline
- 13C — Bounded Counterfactual Observation
- 13D — Unified Outcome Calibration Readmodel

Canonical sahiplik:
- PAPER_CLOSE ve COUNTERFACTUAL_CACHE_OBSERVATION provenance ayrımı
- false-negative / missed-opportunity / avoided-loss ölçümü
- Opportunity Kill Rate
- horizon/follow-up data integrity
- minimum-sample ve class-diversity guardları
- proposal-only calibration

Durum: CLOSED.

---

# PHASE 14 — Command Center & AI Analyst

Amaç: operatöre birkaç saniyede gerçek runtime truth üzerinden karar desteği vermek.

Canonical sahiplik:
- tek canonical panel `app.api.panel:app`
- canonical port 8098
- candidate/universe radar
- paper ledger/accounting/health/intelligence readmodels
- token/pool okunabilir display adı
- Command Center, tactical truth ve operating mode
- AI açıklama/özet/proposal; trade/sign/apply authority yok
- panel read-only authority sınırı

Panel UI kuralı Phase 14 kapsamındadır:
- kullanıcı tarafından kilitlenmiş pencere açıkça unlock edilmeden değiştirilmez
- unrelated full-page replacement yapılmaz
- targeted update → test → panel service restart → HTTP/health → browser review → explicit approval akışı korunur
- UI değişikliği strategy, DB, paper, live, wallet veya signing authority vermez

Token-name repair sahipliği: Phase 5 gerçek metadata'yı üretir/saklar; Phase 14 yalnız bounded readmodel üzerinden gösterir.

Durum: CLOSED.

---

# PHASE 15 — Final Operational Validation & Controlled Micro-Live

Amaç: paper varsayımları ile gerçek execution koşulları arasındaki farkı ölçmek ve yalnız açık kullanıcı onayıyla kontrollü micro-live sınırını yönetmek.

Canonical sahiplik:
- simulation drift validator
- signal-to-block latency/time drift
- realistic gas/slippage/fill/quote delay/execution timing evidence
- paper vs real execution drift
- kill-switch ve çok küçük açık limitler
- live/wallet/signing authority yalnız açık insan onayıyla ve minimum kapsamda

Phase 15 kapanışı herhangi bir live yetkiyi otomatik açmaz.

Durum: CLOSED — FINAL ROADMAP PHASE.

---

## BAKIM SINIFLANDIRMA KURALI

Phase 15 sonrasında çıkan her gerçek bug, iyileştirme veya bakım işi önce bu dosyadaki Phase 0–15 sahipliğine atanır. Ayrı OCR, R-number, post-roadmap, universe-extension, experiment, ERA, V2/V3 veya başka paralel mimari başlığı açılmaz.

Tarihsel ayrıntılı test ve commit kanıtları Git geçmişi ile `TEST_RESULTS.md` ve mevcut phase-scoped validation raporlarında korunur; aktif ROADMAP içinde eski paralel workstreamler tekrar yaşatılmaz.
