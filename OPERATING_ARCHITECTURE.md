# COINOSKOBI — PHASE 0–15 MODULE INTEGRATION ARCHITECTURE

Status: EXISTING ROADMAP MODIFICATION MAP

This document does not create a new Phase, Era, V2/V3, Engine, service family, parallel runtime or second architecture.

Coinoskobi remains one canonical system whose numbered architecture is PHASE 0–15. New capability is added by strengthening the phase where that responsibility already belongs.

## Non-negotiable doctrine

- PHASE 16 is not opened.
- No new Era is opened.
- No new top-level Engine is opened.
- No duplicate pipeline is opened.
- No duplicate panel/runtime is opened.
- Existing PHASE 0–15 modules are modified in place.
- 1 September 2026 is the research/test readiness target, not live-money readiness.
- 1 January 2027 is only the earliest planned live-money transition and still requires separate proof and human approval.
- Live execution, wallet signing and private-key authority remain disabled during the research/test period.
- Raw evidence, derived features, decisions and outcome labels remain separately traceable.
- Missing evidence is explicit; it is never silently converted to zero, success or safe evidence.
- Hindsight reconstruction may not masquerade as an observation.

---

# THE FOUR REQUESTED CAPABILITY GROUPS ARE NOT NEW ARCHITECTURAL MODULES

The user-facing system can be understood in four capability groups, but implementation stays inside PHASE 0–15.

## Capability group A — token universe, observation and paper research

Implemented by strengthening PHASE 0, 1, 2, 3, 5, 7, 8, 11, 12, 13 and 15.

Required behavior:

- existing + newly created token universe
- COLD / WARM / HOT observation
- price, liquidity, volume, transactions and change windows
- DEX-native and WSS evidence
- paper buy/sell simulation
- rejected/watched-candidate counterfactual follow-up
- exact 5m / 15m / 30m / 1h / 6h / 24h outcomes
- MFE / MAE
- entry, rejection, exit and missed-opportunity reasons
- gas, slippage and MEV/execution-cost evidence
- training-quality classification for every record

## Capability group B — external information and market context

Implemented by strengthening PHASE 3, 5, 7, 8 and 10. It is not a separate news Engine.

Required behavior:

- BTC/USDT and ETH/USDT real price + 24h percentage change
- economic calendar / economic pulse
- airdrop / ICO / IDO / launchpad / listing / delisting / unlock events
- project web site / X / Telegram / Discord / CoinMarketCap-style reference research
- DEX / CEX / NEX operational incidents
- hacks, exploits, bridge incidents, withdrawal/deposit pauses, outages and emergency maintenance
- source provenance, publication time, ingestion time, verification state and confidence

## Capability group C — whale, wallet and money-flow intelligence

Implemented primarily by strengthening PHASE 9 and PHASE 14, with PHASE 5/7 consuming the evidence and PHASE 11/13 measuring its forward usefulness.

Required behavior:

- large-holder / whale cohorts
- related-wallet evidence graph
- related sub-wallets only when evidence supports the relationship
- successful DEX-wallet cohort from measurable on-chain history
- DEX analytics + BscScan-derived evidence where appropriate
- accumulation / distribution / inflow / outflow
- CEX / bridge interaction context when observable
- wallet identity and relationship confidence
- wallet-at-entry identity bound to later paper/outcome records

## Capability group D — VEZIR setup

VEZIR is not a new Engine or Phase. VEZIR is the final cross-phase composition of the evidence already produced by PHASE 0–15.

VEZIR is anchored in PHASE 15 as the final shadow composition/readmodel, while its mathematical inputs and learning memory remain owned by their existing phases.

Initial VEZIR mode:

- SHADOW
- READ-ONLY
- PAPER comparison only
- no signing
- no wallet authority
- no live execution authority

---

# PHASE-BY-PHASE MODIFICATION MAP

## PHASE 0 — Critical Bug Fixes / Data Integrity

Add all cross-cutting correctness repairs here, including the current horizon-integrity P0 work.

Responsibilities to strengthen:

- exact token+pool outcome identity
- no scheduler starvation for due checkpoints
- malformed/ambiguous records fail closed
- incomplete historical rows receive explicit quarantine state
- silent data corruption is a blocker

Current PR #21 belongs here.

## PHASE 1 — Core Infrastructure / Durable Evidence Storage

Strengthen the existing SQLite/WAL/storage foundation instead of introducing a new data platform.

Add common evidence metadata where applicable:

- event_id
- entity identity
- source
- source_record_id
- published_at
- observed_at
- ingested_at
- schema_version
- policy/formula version
- quality_state
- confidence
- raw_hash

Raw evidence, derived feature rows and training labels remain logically separate.

## PHASE 2 — Performance & Scalable Pipeline Core

Owns full-universe transport and scheduling.

Strengthen:

- full existing + new pool universe
- bounded discovery and revisit scheduling
- COLD/WARM/HOT observation scheduling
- provider-aware fairness
- exact chain/dex/pool identity
- bounded external-source admission where later phases need it
- no hot-path AI/network blocking that can starve market observation

## PHASE 3 — Risk, Opportunity & Entry Feasibility

Owns pre-entry mathematics.

Strengthen:

- opportunity score
- score confidence / evidence coverage
- expected gross return
- gas estimate
- slippage estimate
- MEV/adverse-execution estimate
- liquidity/position-size feasibility
- expected net edge
- downside/risk budget
- paper position sizing
- entry zone and invalidation conditions

External catalyst/security evidence may influence confidence or risk here only after it has been normalized by its owning observation phase.

Hard safety remains above mathematical score.

## PHASE 4 — Position Lifecycle

Owns capital management after paper entry.

Strengthen existing lifecycle policies rather than creating a new strategy service:

- CLASSIC_RISK_PLAN
- multi-stage TP
- monotonic protective stop
- runner
- CAPITAL_RECOVERY_RUNNER: when mathematically justified, recover principal + measured costs first and continue with profit-funded exposure
- allocation conservation and auditability

## PHASE 5 — DEX Market Intelligence

This remains the primary real-time market observation module and is expanded to hold market-context evidence needed beside DEX-native evidence.

Strengthen:

- pool price/liquidity/volume/transactions
- swap flow, participation, reserve and price-impact evidence
- BTC/USDT and ETH/USDT current price + real 24h percentage change as broad market context
- normalized catalyst/reference observations needed for a token, including listing/unlock/launch information when available
- external market facts remain source-tagged and never masquerade as DEX-native facts

## PHASE 6 — Exit Intelligence

Owns dynamic exit reasoning.

Strengthen:

- momentum exhaustion
- flow deceleration
- price/flow divergence
- liquidity deterioration
- adverse wallet-flow evidence
- VUR_KAC exit behavior: exit when measured supporting evidence decelerates/reverses or the calculated objective is reached
- capital-recovery/runner exit context

No live execution authority is added.

## PHASE 7 — DEX Flow Confirmation & Market Regime

Owns confirmation and regime context.

Strengthen:

- trend/chop/conflict/transition regime
- multi-actor confirmation
- broad-market BTC/ETH context from PHASE 5
- economic-calendar event context as an advisory regime modifier
- expected/actual/previous macro fields where real sources provide them
- central-bank, inflation, employment, GDP and major liquidity-sensitive event timing

Macro events never fabricate a directional signal; they alter context/confidence only through explicit rules.

## PHASE 8 — Native Event Ingestion & Provider Resilience

Owns resilient ingestion mechanics.

Reuse its bounded provider/reconnect/freshness concepts for approved external feeds where practical instead of opening another ingestion architecture.

Strengthen:

- source health
- reconnect/backoff
- freshness/staleness
- duplicate suppression
- source outage classification
- bounded polling/subscription budgets
- provenance-preserving ingest timestamp

Native DEX hot path remains protected from slower external sources.

## PHASE 9 — Wallet / Entity / Smart-Money Intelligence

This is the canonical home for the requested wallet/whale capability.

Strengthen:

- whale cohorts by configurable measurable holdings/value criteria
- wallet behavior features
- related-wallet graph
- KNOWN / STRONG_LINK / WEAK_LINK / UNKNOWN relation states
- successful DEX-wallet cohort based on measured outcomes, not labels alone
- accumulation/distribution
- inflow/outflow
- bridge/CEX interaction evidence when observable
- wallet concentration and multi-wallet participation
- DEX analytics/BscScan inputs with provenance

No identity guessing becomes fact.

## PHASE 10 — Adversary / Scam / MEV Intelligence

This is the canonical home for the highest-priority operational/security news requested by the user.

Strengthen:

- DEX/CEX/NEX hack and exploit events
- bridge exploit/incident events
- withdrawal/deposit freeze
- chain outage
- emergency maintenance
- compromised project/operator evidence
- malicious actor/adversary relationships
- MEV/adverse execution context
- severity, verification and source confidence

Rumor/social evidence stays separate from verified incident evidence.

## PHASE 11 — Learning / Calibration / Outcome Memory

Owns scientific calibration, not execution.

Strengthen:

- feature/outcome calibration
- formula version registry
- probability calibration
- score calibration
- false positive / false negative memory
- avoided loss / missed opportunity memory
- source usefulness calibration
- wallet-signal usefulness calibration
- news/macro/security-signal usefulness calibration
- quality-state aware sample eligibility

No model learns from quarantined/ambiguous data as if it were valid.

## PHASE 12 — Paper Runtime / Paper Lifecycle

All candidate trading policies are compared here before any future live discussion.

Strengthen paper-only comparison of:

- existing canonical policy
- VUR_KAC behavior
- CAPITAL_RECOVERY_RUNNER behavior
- CLASSIC_RISK_PLAN behavior
- calculated position size
- entry zone
- SL/TP/trailing decisions
- measured gas/slippage/MEV assumptions
- exact decision reason and evidence references

## PHASE 13 — Counterfactual / Forward Outcome Observation

This is the canonical training-label layer.

Strengthen:

- watched/rejected-candidate follow-up
- exact token+pool identity
- checkpoint due/overdue priority
- 5m / 15m / 30m / 1h / 6h / 24h forward outcomes
- MFE / MAE
- milestone timing
- missed opportunity
- avoided loss
- paper-vs-non-entry comparison
- explicit VALID / NOT_YET_DUE / PROVIDER_MISSING / FETCH_FAILED / STALE / AMBIGUOUS / INTERNAL_GAP / LEGACY_QUARANTINE semantics

No hindsight price backfill is presented as observed truth.

## PHASE 14 — Wallet Identity → Paper/Outcome Binding & Command-Center Evidence

Preserve the existing entry-time wallet identity binding and expand the readmodel/observability side.

Strengthen:

- wallet/entity identity at decision time
- wallet evidence references persisted with paper entry
- wallet identity bound to later outcome memory
- external event references bound to decision time when used
- panel/readmodel shows source, freshness, confidence and quality state
- no later identity reconstruction presented as entry-time truth

## PHASE 15 — Final Simulation Drift, Cross-Phase Composition & VEZIR Shadow

PHASE 15 remains the final numbered phase and becomes the canonical final composition point. No PHASE 16 follows it.

VEZIR setup is implemented here by composing existing phase outputs, not by creating another engine.

Input ownership remains:

- PHASE 3: entry/risk/net-edge mathematics
- PHASE 4: lifecycle/capital policy
- PHASE 5: market evidence
- PHASE 6: exit evidence
- PHASE 7: confirmation/regime
- PHASE 9: wallet/smart-money evidence
- PHASE 10: adversary/security/MEV evidence
- PHASE 11: calibration/memory
- PHASE 12: paper simulation
- PHASE 13: forward labels/counterfactuals
- PHASE 14: decision-time identity/evidence binding

PHASE 15 output is a reproducible SHADOW decision packet containing at minimum:

- exact candidate identity
- evidence timestamp
- referenced evidence IDs
- opportunity score
- confidence
- calibrated probability when scientifically available
- expected gross return
- gas/slippage/MEV costs
- expected net edge
- downside/risk budget
- recommended paper amount
- entry zone
- SL policy
- TP/runner/VUR_KAC exit policy
- invalidation conditions
- formula/model version
- quality state
- shadow_only=true

It may compare its shadow decision with canonical paper outcomes but receives no live/wallet/signing authority.

---

# EXTERNAL INFORMATION SOURCE RULES

The system may use official sites, X, Telegram, Discord, CoinMarketCap-style references, exchange status/security pages, economic-calendar providers and other approved sources, but every observation must carry provenance and confidence.

Minimum separation:

- VERIFIED_FACT
- CORROBORATED_REPORT
- SINGLE_SOURCE_REPORT
- SOCIAL_CLAIM
- UNKNOWN

A social post is not promoted to verified operational truth without supporting evidence.

---

# DATA/TRAINING ACCEPTANCE

A future VEZIR training dataset is eligible only when:

- identity is exact enough for the record type
- observation and ingestion timestamps are known
- source provenance is known
- schema/policy/formula version is known where applicable
- quality state is explicit
- forward label is actually observed rather than hindsight-invented
- quarantined rows are excluded from normal training
- raw facts can be traced from a derived feature/decision
- paper outcome can be joined back to the exact prior decision and evidence snapshot

SQLite and the current canonical runtime remain preferred until measured load proves they are insufficient.

---

# IMPLEMENTATION ORDER — INSIDE PHASE 0–15 ONLY

1. Close PHASE 0 data-integrity repair represented by PR #21 and verify it on VPS.
2. Strengthen PHASE 1 shared evidence/provenance/quality contract.
3. Strengthen PHASE 5 + PHASE 7 market context: BTC/ETH and economic pulse.
4. Strengthen PHASE 10 operational/security intelligence first because hacks/outages/freezes can invalidate risk assumptions immediately.
5. Strengthen PHASE 5 token catalyst/research observations: launch/listing/airdrop/ICO/IDO and approved social/reference sources.
6. Strengthen PHASE 9 wallet/whale/smart-money tracking and PHASE 14 outcome binding/readmodel.
7. Strengthen PHASE 11/13 training eligibility, calibration and exact forward labels.
8. Strengthen PHASE 3/4/6/12 mathematical entry, sizing and exit policy comparison.
9. Complete VEZIR shadow composition in PHASE 15.

At no point does this sequence create a new Phase, Era, Engine, duplicate runtime, duplicate pipeline or live authority.
