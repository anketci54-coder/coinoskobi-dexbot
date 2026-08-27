# COINOSKOBI — FOUR-ENGINE OPERATING ARCHITECTURE

Status: POST-ROADMAP OPERATING MODEL

This document does not open Phase 16. It defines the post-roadmap operating architecture for research, paper simulation, data collection and future AI training.

## Program doctrine

- 1 September 2026 target: research/test platform readiness only.
- Earliest planned real-money transition: 1 January 2027, subject to separate proof and human approval.
- Live execution, wallet signing and private-key authority remain disabled.
- Raw evidence is preserved. Derived features, scores and labels are stored separately.
- Missing data is never silently treated as zero or valid evidence.
- Every training-relevant record must retain provenance, timestamps, schema/policy version and quality state.
- No hindsight reconstruction is allowed to masquerade as an observed outcome.

---

# ENGINE 1 — UNIVERSE / MARKET LAB

Purpose: discover and continuously observe the existing + new token universe, classify market state, run paper simulations and produce deterministic forward outcomes.

Core responsibilities:

- full-universe registry
- COLD / WARM / HOT state machine
- price, liquidity, volume, transaction and change windows
- native WSS / on-chain event evidence
- risk / sellability / MEV observations
- paper trade lifecycle
- counterfactual non-entry tracking
- 5m / 15m / 30m / 1h / 6h / 24h outcomes
- MFE / MAE and milestone events
- entry / exit / rejection reasons
- gas, slippage and execution-cost estimates

Canonical identity:

- token: chain + token
- pool: chain + dex + pool
- observation: source + chain + dex + pool + observed_at

Training rule:

No row is training-eligible unless its required identity, provenance and timing fields are valid and its quality state is explicit.

---

# ENGINE 2 — EXTERNAL INTELLIGENCE

Purpose: monitor the external information environment and convert heterogeneous news/social/economic events into normalized evidence.

## 2A Major market context

- BTC/USDT
- ETH/USDT
- current price
- 24h percentage change
- source and freshness

## 2B Economic pulse

- major macro calendar events
- central-bank events
- inflation / employment / GDP / liquidity-relevant releases
- expected / actual / previous where available
- importance and timing

## 2C Launch / distribution intelligence

- airdrop
- ICO
- IDO
- launchpad
- listing / delisting
- token unlock / distribution events where relevant

## 2D Token research intelligence

Potential sources:

- official web site
- X
- Telegram
- Discord
- CoinMarketCap / equivalent reference sources
- project documentation / announcements

Every item must preserve source provenance and verification state. Social claims are not equivalent to verified operational facts.

## 2E Exchange / protocol operations and security

Highest-priority external event class:

- DEX / CEX / NEX operational incidents
- hacks / exploits
- bridge incidents
- withdrawals paused
- deposits paused
- chain outages
- contract migrations
- emergency maintenance
- delistings / forced market changes

Normalized event minimum:

- event_id
- event_type
- entity / exchange / chain / token references
- source
- published_at
- observed_at
- ingested_at
- verification_state
- confidence
- severity
- raw_hash
- schema_version

---

# ENGINE 3 — WALLET / MONEY-FLOW INTELLIGENCE

Purpose: determine where capital is moving and whether observed market moves are supported by whale, smart-money or broader wallet behavior.

## 3A Whale inventory

- wallets above configurable asset/value thresholds
- asset concentration
- inflow / outflow
- accumulation / distribution
- bridge / exchange interaction

## 3B Related-wallet graph

Relationship states:

- KNOWN
- STRONG_LINK
- WEAK_LINK
- UNKNOWN

No identity guess is promoted to fact without evidence.

## 3C Successful DEX-wallet cohort

Candidate discovery sources may include DEX analytics and BscScan-derived on-chain evidence.

Wallet quality is measured from observed history, not reputation labels alone:

- realized / marked outcomes where measurable
- consistency
- drawdown
- holding time
- token-selection behavior
- entry timing
- exit timing
- repeat participation

## 3D Money-flow output

Primary question:

"Where is capital moving, how fast, through which wallets/entities, and with what confidence?"

Outputs are evidence only; they do not create execution authority.

---

# ENGINE 4 — VEZIR FUSION / DECISION SCIENCE

Purpose: fuse evidence from Engines 1-3 and produce a scientifically auditable shadow decision packet.

Initial mode: SHADOW / READ-ONLY / NO EXECUTION AUTHORITY.

Pipeline:

RAW EVENTS
-> NORMALIZATION
-> QUALITY + PROVENANCE
-> FEATURE LAYER
-> VEZIR FUSION
-> DECISION PACKET
-> PAPER SIMULATION
-> FORWARD OUTCOMES
-> TRAINING LABELS

## Decision packet

Minimum fields:

- candidate identity
- evidence timestamp
- opportunity score
- confidence
- estimated success probability
- expected gross return
- expected gas
- expected slippage
- expected MEV / adverse execution risk
- expected net edge
- downside estimate
- recommended paper position size
- entry zone
- stop-loss policy
- take-profit / exit policy
- invalidation conditions
- evidence references
- model / formula version
- shadow_only=true

## Core mathematical principles

Example net-edge form:

Net Edge = Expected Return - Gas - Slippage - MEV Cost - Failure/Risk Cost

Example position-sizing form:

Position Size = Capital x Risk Budget x Confidence x Liquidity Factor x Edge Factor

Coefficients and thresholds must be calibrated from observed Coinoskobi data. They are not invented from hindsight.

## Exit policy families

### VUR_KAC

Enter only when measured momentum / flow / acceleration evidence supports it. Exit when the expected move is achieved or the supporting indicators decelerate / reverse.

### CAPITAL_RECOVERY_RUNNER

Recover principal + measured execution costs first when conditions permit; keep the remaining profit-funded position under trailing / flow / regime conditions.

### CLASSIC_RISK_PLAN

Mathematical stop, staged targets and optional trailing logic.

Vezir may compare these policies in shadow simulation before any future authority discussion.

---

# SHARED DATA CONTRACT

Every training-relevant raw/event record should carry, where applicable:

- event_id
- entity_id / token / pool / wallet
- chain
- dex / venue
- source
- source_record_id when available
- published_at when applicable
- observed_at
- ingested_at
- schema_version
- policy_version
- quality_state
- confidence
- raw_hash

Quality states must be explicit. Suggested baseline vocabulary:

- VALID
- NOT_APPLICABLE
- NOT_YET_DUE
- PROVIDER_MISSING
- FETCH_FAILED
- STALE
- AMBIGUOUS
- INTERNAL_GAP
- LEGACY_QUARANTINE

Silent NULL is not sufficient for training eligibility.

---

# IMPLEMENTATION ORDER

## Gate 0 — Data integrity closure

Finish and validate PR #21 before changing the VPS runtime. Required:

- due/overdue-first durable follow-up
- exact token+pool observation identity
- legacy incomplete outcome quarantine
- full regression PASS
- VPS post-apply verification

## Workstream A — Shared evidence contract

Build the common event/provenance/quality contract first so Engines 2 and 3 do not create incompatible datasets.

Acceptance:

- deterministic schema
- timestamp semantics defined
- explicit quality states
- raw/derived separation
- no execution authority

## Workstream B — External intelligence minimum viable feed

Order:

1. BTC/USDT + ETH/USDT real market context
2. economic calendar
3. exchange/protocol operational + hack events
4. token research / social evidence
5. ICO/IDO/airdrop radar

Priority rationale: 2E can invalidate risk assumptions fastest, so it is implemented before broad social expansion.

## Workstream C — Wallet / money-flow intelligence

Order:

1. wallet evidence schema
2. whale threshold cohorts
3. wallet relation graph
4. successful DEX-wallet cohort
5. money-flow aggregation and confidence

## Workstream D — Vezir shadow setup

Order:

1. feature registry
2. formula/version registry
3. evidence fusion contract
4. shadow decision packet
5. paper-policy comparison
6. forward-outcome evaluation
7. calibration dataset export

No AI model training starts until the dataset integrity gate is satisfied.

---

# ACCEPTANCE STANDARD

The architecture is considered research-ready only when:

- Engines 1-3 produce provenance-complete data
- missing/failed observations are explicitly classified
- Vezir consumes evidence without fabricating missing inputs
- every decision packet is reproducible from stored evidence + formula/model version
- paper outcomes can be joined to the exact prior decision and exact market entity
- live/wallet/signing/execution authority remains false

This operating model is intentionally modular but not microservice-heavy. SQLite and the existing runtime remain preferred until measured load proves a need for a more complex storage or messaging layer.
