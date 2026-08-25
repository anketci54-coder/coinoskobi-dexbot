# Coinoskobi DexBot

**Professional Modular DEX Decision Support Platform**

Coinoskobi, DEX piyasalarında fırsat keşfi, risk analizi, kısa-horizon piyasa
gözlemi, karar desteği ve güvenli işlem yaşam döngüsü geliştirmek için
oluşturulan modüler bir platformdur.

Temel ilke:

**Karar kalitesi, güvenlik ve doğrulanmış veri; işlem sıklığından önce gelir.**

---

## Current Project State

- **Phase 0–15: CLOSED**
- **Phase 16: NOT OPENED**
- Current mode: **post-roadmap operation / maintenance**
- Current production focus: **BNB Chain (BSC) + PancakeSwap**
- Token/pair universe size is dynamic and MUST NOT be hardcoded.
- Current canonical functional commit before this documentation sync:
  `cd6348e64c23559334a04c967c805646bf4045ae`
- Final VUR_KAC reconciliation full regression:
  **1005 passed / 0 failed**
- Final maintenance critical audit:
  **51 passed / 0 failed**
- New paper positions default to **VUR_KAC**.
- Raw market observation history is append-only.
- EWMA/CUSUM streaming math is isolated by pool and source.
- Calibration is derived from observed history and remains authority-free.
- Live execution authority: **0**
- Wallet/signing authority: **0**
- AI trade authority: **0**
- Paper runtime acceptance after integration: **PASS**
- Panel remained running and was not restarted during paper deployment.

## Post-Roadmap Integration Status

Current integrated maintenance includes:

- exact AMM / price-impact mathematics
- empirical exit-capacity evidence
- Beta-Binomial flow estimation
- HHI / Shannon wallet concentration measurements
- expected MEV-loss evidence
- rug feature evidence
- empirical ES/CVaR
- data-derived fractional Kelly sizing
- pool/source isolated streaming state
- append-only raw market history
- history-derived EWMA/CUSUM calibration
- canonical VUR_KAC paper-policy binding

Current observation expansion is intentionally focused on the dynamic
**BSC + PancakeSwap** universe.

Future observation enrichment may include real provider-backed:

- market cap
- price
- age
- transactions
- volume
- traders
- 5m / 1h / 6h / 24h movement
- liquidity
- gainers / losers

The whole universe must not be processed at expensive hot-path frequency.
Broad COLD observation, moving WARM candidates and anomalous HOT candidates
are the intended operating model.

See `PROJECT_STATE.md` for the canonical continuation checkpoint.

---

## Vision

Coinoskobi'nin hedefi yalnızca token bulmak değildir.

Sistem:

- yeni fırsatları mümkün olduğunca erken gözlemlemeli
- gerçek talep ile yapay hareketi ayırmaya çalışmalı
- likidite ve satış riskini sürekli izlemeli
- kısa zaman aralıklarında piyasa davranışını ölçmeli
- işlem açıldıktan sonra da ürünü izlemeye devam etmeli
- risk koşulları bozulursa pozisyon yönetimine gerekli sinyali vermeli
- gerçek para kullanılmadan önce tüm davranışları paper/sandbox ortamında
  doğrulamalıdır

---

## Core Principles

- BSC-first architecture
- modular design
- deterministic safety rules
- bounded external work
- short-horizon observation
- cache/local-first processing
- no silent authority escalation
- paper-first execution development
- risk gates before execution
- explicit unknown states
- clean repository
- measurable validation

---

## Current Architecture

Coinoskobi'nin mevcut ana veri akışı:

1. **Market / DEX Sources**
2. **Scanner / Source Adapters**
3. **Normalization / Ingress**
4. **Candidate Admission Queue**
5. **Bounded Work Scheduler**
6. **Analysis Pipeline**
7. **DEX Market Intelligence**
8. **Risk Engine / Safety Gates**
9. **Deterministic Strategy / Decision Support**
10. **Execution Context**
11. **Position Lifecycle**
12. **Paper / Future Execution Boundary**

Analysis Pipeline içinde:

- Contract Analysis
- Token Analysis
- Pair Analysis

DEX Market Intelligence içinde:

- Market Clock
- Swap Flow
- Market Quality
- Flow Acceleration
- Wallet Flow
- Reserve Dynamics
- Price Impact
- Signal Bundle

External data acquisition, analysis, decision authority and execution
authority are separate responsibilities.

---

## Current Modules

### Scanner

Responsibilities:

- external pool discovery
- source-specific reads
- bounded HTTP behavior
- retry / timeout control

Current source support includes GeckoTerminal.

---

### Source / Candidate Pipeline

Responsibilities:

- source normalization
- chain-aware candidate identity
- ingress filtering
- duplicate collapse
- bounded admission
- prioritization
- queue management
- cooldown protection
- scheduler fairness

---

### Cache

Responsibilities:

- repeated expensive work reduction
- analyzer result caching
- market data reuse
- bounded external work

SQLite is currently used for local cache/state storage.

---

### Analyzer

Current analysis areas include:

- token analysis
- pair analysis
- bytecode / contract capability analysis
- source evidence processing

---

### Risk Engine

Risk is a hard safety layer.

Current areas include:

- honeypot / sellability protection
- mint capability risk
- pause / blacklist style contract capability risk
- liquidity context
- trade-size / liquidity exposure
- MEV-related exposure context
- execution-cost inputs
- deterministic gate decisions

A favorable score must not bypass a hard safety gate.

---

### Strategy / Decision Support

Decision logic is deterministic.

The strategy layer may produce outcomes such as:

- candidate rejection
- observation
- paper candidate context
- future execution context

Decision support does not automatically grant execution authority.

AI, if added later, remains advisory unless a future explicit architecture
decision changes that boundary.

---

## DEX Market Intelligence

Phase 5 establishes the short-horizon DEX observation foundation.

Implemented event contracts include:

- PairCreated
- Swap
- Sync
- Mint
- Burn

Implemented analysis areas include:

- normalized DEX events
- market clocks
- swap-flow mechanics
- buy/sell imbalance
- market participation
- liquidity quality
- reserve deterioration
- concentrated-volume detection
- flow acceleration
- wallet-flow concentration
- price-impact context
- unified DEX signal bundle

Real aggregate DEX compatibility has been validated with bounded
GeckoTerminal reads.

Native BSC Swap/Sync streaming is not yet claimed as validated.

---

## Market Clocks

Coinoskobi does not rely only on traditional 5m / 15m / 1h candles.

The system supports short-horizon observation clocks.

### Wall Clock

- 250 ms
- 500 ms
- 1 s
- 2 s
- 5 s
- 10 s
- 30 s

### Block Clock

- 1 block
- 2 blocks
- 4 blocks
- 8 blocks
- 16 blocks
- 32 blocks

### Swap Clock

- 5 swaps
- 10 swaps
- 25 swaps
- 50 swaps
- 100 swaps

These clocks are observation windows.

They are not execution permissions.

---

## Position Lifecycle

Phase 4 established the mechanical position-management core.

Implemented:

- position lifecycle contract
- deterministic state machine
- TP1
- TP2
- TP3
- runner allocation
- duplicate TP protection
- no TP skipping
- fraction conservation
- monotonic protective trailing stop
- highest-price tracking
- runner exit-candidate mechanics

Current allocation:

- TP1: 20%
- TP2: 25%
- TP3: 25%
- Runner: 30%

The position lifecycle core does not by itself grant paper or live
execution authority.

---

## Vur-Kac Direction

Coinoskobi includes a planned controlled short-opportunity mode.

The Vur-Kac concept is not blind auto-trading.

Expected behavior:

- short-horizon opportunity detection
- strict entry conditions
- single take-profit target
- mandatory protective stop
- liquidity / sellability / slippage checks
- continuous post-entry observation
- fast exit when market quality deteriorates
- no bypass of hard risk gates

Exact production rules must be validated in their own future phase before
execution authority is enabled.

---

## Authority and Safety Boundaries

Observation authority and execution authority are different.

Current default boundaries:

- decision support does not equal trade permission
- scoring does not override hard safety
- market intelligence does not sign transactions
- no wallet signing authority
- no implicit live execution authority
- provider failures remain failures / unknown
- missing evidence must not silently become safe evidence
- sellability remains a required safety concern
- liquidity remains a required safety concern

Private keys, seed phrases and wallet secrets must never be committed to
the repository.

---

## Development Workflow

Normal development order:

1. Roadmap phase plan
2. Implementation
3. Targeted tests
4. Smoke tests
5. End-to-end tests
6. Connection regression
7. Full regression
8. Compile / integrity checks
9. Phase validation
10. Phase closure
11. Next phase plan
12. Commit / push

A phase must not be marked `CLOSED` before its required validation is
complete.

---

## Roadmap Governance

`ROADMAP.md` is Coinoskobi's chronological living development plan.

Mandatory rules:

1. Phases remain in chronological order:

   `Phase 0 -> Phase 1 -> Phase 2 -> ...`

2. Every roadmap item belongs inside its own phase.

3. Before a phase begins, its section contains:
   - purpose
   - planned scope
   - decisions still requiring evaluation
   - expected result

4. When a phase finishes, the entire roadmap is not rewritten.

5. Only the closing phase is updated with:
   - actual completed scope
   - permanent decisions actually taken
   - concise validation result
   - known gaps
   - deferred work
   - final phase status

6. During the same closure cycle, the next phase gets its initial plan in
   its own chronological position.

7. Previously closed phases are not changed during normal later-phase
   updates.

8. Future phases are not changed without a concrete reason.

9. Planned decisions and accepted decisions are different.

10. A phase is not marked `CLOSED` before required validation completes.

11. Valid status examples:
    - WAITING
    - ACTIVE
    - IN VALIDATION
    - CLOSED

12. ROADMAP does not store complete terminal logs, temporary probes,
    debug transcripts or disposable audit scripts.

13. Legacy / superseded phase numbering must not return to the active
    chronological roadmap.

14. Core rule:

    **Everything goes to its proper place; nothing unrelated changes.**

---

## Roadmap Boundary

The numbered roadmap currently runs from Phase 0 through Phase 15.

A Phase 16 is not automatically created.

After the numbered roadmap is completed, normal project development may
continue through:

- releases
- milestones
- sprints
- patches
- hotfixes

---

## Documentation

Primary project documents:

- `README.md`
- `ROADMAP.md`
- `CONSTITUTION.md`
- `PROJECT_STATUS.md`
- `CHANGELOG.md`
- `ARCHITECTURE.md`
- `CONTRIBUTING.md`
- `TEST_RESULTS.md`

`README.md` explains the project and its permanent development rules.

`ROADMAP.md` contains the chronological phase plan, decisions, closures
and next planned work.

---

## Repository Structure

Main project areas:

- `app/analyzer/`
- `app/api/`
- `app/cache/`
- `app/chains/`
- `app/config/`
- `app/dex/`
- `app/filter/`
- `app/paper/`
- `app/pipeline/`
- `app/risk/`
- `app/scanner/`
- `app/strategy/`
- `data/`
- `tests/`

Main entry point:

- `main.py`

---

## Development Rules

- one responsibility per module
- no unnecessary duplication
- no dead code
- no disposable scripts left behind
- bounded external work
- deterministic safety boundaries
- targeted tests for new behavior
- smoke / E2E testing before closure
- full regression before closure
- compile before commit
- DB integrity checks where relevant
- clean repository before phase seal
- small understandable changes
- stable main branch
- no unrelated modifications during phase closure

---

## Security

Never commit:

- private keys
- seed phrases
- wallet secrets
- exchange API secrets
- provider secrets

Future wallet or exchange integrations require an explicit separate
implementation and validation phase.

---

## Technologies

Current core stack includes:

- Python 3
- SQLite
- Web3.py
- FastAPI
- GeckoTerminal
- BNB Chain
- PancakeSwap
- pytest

---

## License

Private Repository.

All Rights Reserved.

---

## Dynamic Mathematical Trade Planning Rule

Coinoskobi'nin kalıcı işlem-planlama kuralı şudur:

**Coinoskobi hiçbir score, sermaye miktarı, entry, SL, TP seviyesi veya TP'de realize edilecek pozisyon oranını keyfi sabitlerle belirleyemez. Tüm karar değerleri doğrulanmış piyasa, onchain, likidite, flow, risk ve execution-cost verilerinden açık, izlenebilir ve tekrar üretilebilir matematiksel modellerle türetilir. Eksik kanıt sayı uydurmaz; `UNKNOWN` üretir.**

Bu kural aşağıdaki davranışları zorunlu kılar:

1. Keyfi score ağırlığı, magic-number threshold, sabit SL/TP yüzdesi veya sabit satış oranı nihai karar kuralı olamaz.
2. Üretilen her score doğrulanmış girdilere, açık matematiksel hesaba, veri kaynağına, freshness bilgisine ve evidence coverage'a dayanmalıdır.
3. Sistem elindeki uygun token, pair, onchain, liquidity, reserve, flow, contract, risk ve maliyet verilerini mümkün olduğunca hızlı işleyerek tek bir dinamik işlem planı üretmelidir.
4. İşleme ayrılacak sermaye cüzdanın keyfi sabit yüzdesiyle değil; ölçülen downside, exit capacity, likidite derinliği, price impact, volatilite, gas, slippage, tax, MEV ve gerçek net kayıp kapasitesinden matematiksel olarak türetilmelidir.
5. Entry tek bir keyfi yüzde veya sabit uzaklıkla belirlenmez; mevcut piyasa yapısı, reserve davranışı, kısa-horizon momentum/flow, volatilite, likidite eğrisi, price impact ve beklenen net edge üzerinden hesaplanır.
6. İlk SL sabit yüzde değildir. Piyasa yapısından türetilir ve pozisyon ilerledikçe trend, volatilite, peak, reserve, flow ve liquidity değişimine göre yeniden hesaplanır. Long pozisyonda koruyucu SL aşağı gevşemez; yalnız aynı kalabilir veya yukarı taşınabilir.
7. TP1'e ulaşıldığında satılacak pozisyon miktarı sabit bir yüzde değildir. Sistem, başlangıçta üstlenilen gerçek net riski azaltmak veya nötralize etmek için gerekli minimum realizasyon miktarını matematiksel olarak hesaplar.
8. TP2'ye ulaşıldığında satılacak miktar yeniden hesaplanır. Dinamik SL'nin zaten garanti ettiği net kâr dikkate alınır; yalnız korunması gereken fakat henüz korunmayan kâr kadar pozisyon realize edilir. Gerekli matematiksel sonuç sıfır ise TP2'de satış yapılması zorunlu değildir.
9. TP3 klasik sabit take-profit değildir. TP1 ve TP2 sonrasında kalan pozisyon trend runner olarak taşınır. Runner; peak, momentum, acceleration, buy/sell flow, reserve health, liquidity, volatility, execution cost ve exit feasibility ile sürekli yeniden değerlendirilir.
10. Runner'ın amacı teorik tepeyi önceden tahmin etmek değil; trend bozulmasını mümkün olduğunca doğru ve geç yakalayarak matematiksel olarak mümkün olan ölçüde tepeye yakın net çıkış üretmektir.
11. Gas, slippage, tax, MEV, price impact ve çıkış maliyetleri hesaba katılmadan brüt getiri tek başına işlem avantajı olarak kabul edilmez. Karar motoru net sonucu esas alır.
12. Her işlem planı en az şu çıktıları açıklayabilmelidir: gir/girme, kullanılacak sermaye, entry veya entry bandı, initial SL, current dynamic SL, TP1 seviyesi ve realize miktarı, TP2 seviyesi ve realize miktarı, runner miktarı, beklenen net P&L, exit capacity, kullanılan veriler ve matematiksel karar gerekçesi.
13. Hard safety gate her zaman matematiksel fırsat sonucundan üstündür. Confirmed hard-risk uygun görünen score, trend veya beklenen kâr ile override edilemez.
14. Veri eksikse sistem sayı veya güven üretmez. Eksik alan `UNKNOWN` olarak korunur ve karar modeli bunu açıkça taşır.

Bu kural, geçmişte uygulanmış sabit mekaniklerin tarihsel kaydını silmez; ancak gelecekteki işlem-planlama ve pozisyon-yönetimi geliştirmelerinde keyfi sabitler yerine veri-türevli matematiksel modellerin hedef mimari olduğunu tanımlar.
