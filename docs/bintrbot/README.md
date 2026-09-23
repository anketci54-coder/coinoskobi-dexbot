# BINTRBOT

## Project Identity

BINTRBOT is a Binance TR-focused market data, research, risk and execution platform.

Primary execution venue:

**BINANCE TR**

Current active market universe:

**TR-MARKET / TRY-CORE**

Current phase:

**FAZ 0 — DATA FOUNDATION**

Canonical roadmap:

**docs/bintrbot/ROADMAP.md**

---

## Canonical Boot Protocol

Every new BINTRBOT work session must begin in this order:

1. Read this file completely.
2. Read `docs/bintrbot/ROADMAP.md`.
3. Verify current runtime state on the server.
4. Verify active services and data freshness.
5. Verify current phase and its exit gates.
6. Continue only from the next incomplete canonical step.

Do not continue from AI memory, assumptions, old chat summaries or stale screenshots when current repository/runtime evidence is available.

---

## Source of Truth Order

Use this order:

1. **Current server runtime and generated data**
2. **Current local project files**
3. **Git state / current branch**
4. **GitHub canonical files**
5. **Previous chat context / AI memory**

When sources conflict, prefer the highest available source in this list.

---

## Current Server Project

Expected project root:

`/root/bintrbot`

Current data architecture:

`RAW / BRONZE → SILVER → GOLD`

Current storage formats include:

- Parquet
- Zstd compression
- JSONL/Zstd for live raw streams
- manifests
- SHA256 checksums

---

## Current Runtime Services

Expected active market-data services:

- `bintrbot-collector.service`
- `bintrbot-backfill-klines.service`

Historical aggregate-trade backfill:

- `bintrbot-backfill-aggtrades.service`

This service may intentionally be stopped while kline backfill is using the Binance TR API budget.

Service state alone is not sufficient.

Always distinguish:

- `SERVICE_ACTIVE`
- `DATA_FRESH`

An active service with stale data is not healthy.

---

## Current Known Snapshot

Snapshot date:

**2026-09-23**

Observed current TRY market count:

**308**

This is a dated snapshot, not a permanent market-universe fact.

Known data-quality case:

`ALGO_TRY / 2023-03 → gap=1`

This must be verified during **FAZ 1 — DATA INTEGRITY & OPERATIONS**.

---

## Current Canonical Focus

Until CHECKPOINT A, active development scope is frozen to:

- FAZ 0 — Data Foundation
- FAZ 1 — Data Integrity & Operations
- FAZ 2 — Data Lake + MVP Features
- FAZ 3 — TR Market Intelligence
- CHECKPOINT A — First Baseline Evidence

New ideas do not automatically become active work.

They go to backlog unless required to complete an active phase exit gate.

---

## Fast Path

BINTRBOT does not require the full intelligence platform before Paper Trading.

If the baseline is promising:

`FAZ 0 → FAZ 1 → FAZ 2 → FAZ 3 → CHECKPOINT A → FAZ 12 → FAZ 13`

Therefore the following are **not mandatory prerequisites** for the first Paper test:

- wallet intelligence
- on-chain intelligence
- DEX intelligence
- Obsidian
- token lifecycle intelligence
- event intelligence
- Binance Global radar
- AI models

They are added only when they show measurable incremental value.

---

## Strategy-Dependent Data Rule

A missing dataset must not block a strategy that does not use it.

Example:

A kline-only baseline does not require full historical aggTrades completion.

Trade-flow strategies do require aggTrades.

Order-book strategies require valid L2 data for the period being tested.

Data requirements must be explicitly defined per strategy.

---

## Historical L2 Rule

Do not invent historical order-book data.

If true historical L2 does not exist:

- do not reconstruct it as fact
- do not present estimated spread as observed spread
- do not present estimated slippage as observed slippage

Any approximation must be explicitly marked:

`MODEL_ASSUMPTION`

Real L2 evidence begins from the time BINTRBOT started recording it.

---

## Point-in-Time Rule

BINTRBOT uses point-in-time and bitemporal principles.

Important fields include:

- `EVENT_TIME`
- `VALID_FROM`
- `VALID_TO`
- `OBSERVED_AT`
- `INGESTED_AT`
- `KNOWN_AT`
- `SYSTEM_VALID_FROM`
- `SYSTEM_VALID_TO`

A corrected record must not silently overwrite historical knowledge.

If:

`KNOWN_AT > SIMULATION_TIME`

the information must not be used in that simulation.

---

## Historical Universe Rule

Today's active market list must never be projected backward into historical backtests.

Historical testing must use the market universe that was actually tradable at the simulated time.

Delisted markets should be included when reliable historical evidence is available.

If inaccessible, the limitation must be explicitly reported.

---

## Identity Rule

Symbols are not permanent identities.

Canonical entities include:

- `ASSET_ID`
- `MARKET_ID`
- `CONTRACT_ID`
- `CHAIN_ID`
- `ENTITY_ID`
- `WALLET_ID`
- `EVENT_ID`
- `SOURCE_ID`

Contract migration does not automatically mean the same asset.

Economic continuity must be evaluated.

Possible result:

- `SAME_ASSET`
- `NEW_ASSET`
- `UNCERTAIN`

---

## Data Quality Rules

Never:

- fabricate data
- silently forward-fill missing market data
- hide gaps
- hide duplicates
- use future information in historical simulation
- overwrite historical knowledge without versioning
- invent causes for price moves
- treat assumptions as observations

Required:

- provenance
- checksums
- manifests
- dataset versioning
- explicit quality flags
- fail-closed behavior for critical integrity failures

If source data does not exist:

`SOURCE_DATA_UNAVAILABLE`

If historical data cannot be obtained:

`HISTORICAL_DATA_UNAVAILABLE`

If a cause cannot be supported:

`CAUSE_UNKNOWN`

---

## Train / Validation / Final Test

Use separate chronological periods:

- TRAIN
- VALIDATION
- FINAL_TEST

Feature and threshold selection belongs in VALIDATION.

FINAL_TEST must remain as untouched as possible.

Repeatedly changing the model after looking at FINAL_TEST invalidates it as a true final test.

All experiments must be recorded with dataset version and date ranges.

---

## Risk Rule

Risk is designed from the beginning even though real execution is opened later.

Risk architecture includes:

- position sizing
- max exposure
- liquidity requirements
- spread ceiling
- slippage ceiling
- daily loss limit
- stop policy
- authority boundaries
- kill switch

AI has no unlimited trading authority.

Real order authority is enabled only in the controlled execution phases.

---

## Wallet Intelligence Rules

When wallet intelligence is later enabled:

- no unsourced wallet labels
- no invented wallet relationships
- every relationship requires evidence and method
- confidence requires evaluation timestamp
- survivorship bias is forbidden
- unrealized PnL is not realized PnL
- transfer is not automatically a trade
- exchange internal movement is not automatically market flow
- unknown cost basis means unknown true PnL
- only information known at the simulated time may be used

Obsidian, if later enabled, is a research/graph layer only.

Canonical truth remains in structured data such as SQL/Parquet.

---

## Execution Progression

Execution authority progresses only through explicit gates:

1. Read-only
2. Research / replay
3. Paper Trading
4. Manual Assisted
5. Controlled Auto Trading

Secrets must never be committed to GitHub, logs, datasets or chat.

---

## Phase Completion Rule

A phase is not complete because code exists.

Each phase must satisfy its required exit gate, including as applicable:

- `SCOPE_COMPLETE`
- `REQUIRED_TESTS_PASS`
- `REQUIRED_DATA_QUALITY_PASS`
- `FAILURE_RECOVERY_PASS`
- `KNOWN_LIMITATIONS_RECORDED`
- `SOURCE_PROVENANCE_COMPLETE`
- `NO_UNRESOLVED_CRITICAL_ERROR`

The exact required data scope is strategy-dependent.

---

## Canonical Principle

**First identity.  
Then correct time.  
Then historical universe.  
Then real data.  
Then data integrity.  
Then a small testable hypothesis.  
Then the first baseline.  
If the baseline is promising, the Paper path stays open.  
Enrichment is added only when its incremental value is measured.  
Risk is designed from the start.  
Execution is opened last.**

Active market universe:

**TR-MARKET / TRY-CORE**
