# COINOSKOBI FULL-UNIVERSE OBSERVATION ARCHITECTURE

Status: CANONICAL DESIGN LOCKED  
Date: 2026-08-25  
Base: `main@e55c2f5b7ef97e20f5674f9e9bdd195c5aeff73a`

## 1. Scope and authority

This is a post-roadmap extension of the canonical observation/data layer.

It does **not** open Phase 16, a new Era, V2/V3, a second runtime, a second
panel, or a parallel trading architecture.

Current scope:

- chain: BNB Chain (BSC)
- DEX universe: PancakeSwap V2 and V3
- execution: PAPER only
- AI authority: 0
- live execution authority: 0
- wallet/signing authority: 0

The universe size is dynamic. No observed count such as 25,000 or 25,406 may
be hardcoded.

## 2. Canonical doctrine

Every discovered PancakeSwap V2/V3 pool remains represented in one durable
Universe Registry.

`COLD`, `WARM`, and `HOT` describe **market seismic behavior only**:

- COLD: broad-universe, low-cost periodic observation
- WARM: meaningful movement; shorter observation interval
- HOT: anomalous or rapidly moving; deep/native observation eligible

Liquidity and age are profile facts. They do not remove an otherwise valid
PancakeSwap pool from the universe.

A rejected/deferred pool remains in the registry and may become active again
after later evidence.

Heavy security, RPC, WSS, mathematical, analyzer, or VUR_KAC work is never
run across the whole universe. Only the bounded WARM/HOT frontier may consume
that budget.

## 3. Provider roles

### Universe identity

On-chain PancakeSwap V2/V3 pool-creation history is the canonical source of
universe membership.

Discovery has two idempotent branches:

1. EXISTING backfill: bounded block-range historical scan with durable
   checkpoint
2. NEW tail: incremental pool-creation ingestion after the checkpoint

The two branches write the same registry and cannot create two architectures.

### Market snapshots

DexScreener official batch endpoints provide cheap indexed market snapshots
in batches of at most 30 token/address identities per request.

DexScreener is not the source of complete universe identity and no private or
internal website endpoint is used.

Existing GeckoTerminal exact-pool snapshot support may remain temporarily as
a bounded compatibility/follow-up provider while migration is in progress.
Its `/new_pools` feed must not remain canonical discovery after cutover.

### Deep evidence

HOT candidates may progress to existing native WSS/on-chain, security,
streaming math, admission, strategy, and VUR_KAC paths. Missing evidence
remains UNKNOWN. Explicit proven danger may veto.

## 4. Canonical data flow

```text
Pancake V2/V3 creation history
  -> EXISTING backfill + NEW tail
  -> UniverseRegistry
  -> due-observation scheduler
  -> bounded DexScreener batches
  -> raw market observation history
  -> SeismicClassifier
  -> COLD / WARM / HOT
  -> bounded WARM/HOT priority queue
  -> HOT deep evidence
  -> existing final admission
  -> PAPER_BUY / WATCH / REJECT
```

`REJECT` is a decision state, not deletion from the observation universe.

## 5. Canonical files and classes

Initial canonical package:

- `app/universe/schema.py`
  - schema version and market-state constants
  - address/state normalization
- `app/universe/registry.py`
  - `UniverseRegistry`
  - durable idempotent pool registration
  - discovery checkpoints
  - latest profile/state storage
  - due-observation reads
- `app/universe/discovery.py`
  - `PancakeUniverseDiscovery`
  - bounded V2/V3 EXISTING backfill and NEW tail
  - no market-quality filtering
- `app/universe/snapshot.py`
  - `DexScreenerSnapshotClient`
  - strict official batch bound of 30
  - normalized real market facts
- `app/universe/seismic.py`
  - `SeismicClassifier`
  - evidence-backed COLD/WARM/HOT transitions
  - no invented probability
- `app/universe/scheduler.py`
  - `UniverseObservationScheduler`
  - bounded due-work selection and promotion priority
- `app/universe/runtime.py`
  - `FullUniverseObservationRuntime`
  - single lifecycle owner/composition boundary

Tests mirror these files under `tests/universe/`.

The first implementation unit is only `schema.py`, `registry.py`, and their
tests. It is passive and is not wired into the production runner until its
migration/idempotency/bounded-read tests pass.

## 6. SQLite schema

The canonical store remains the existing cache database
`data/cache/cache.db`. A second competing cache database is prohibited.

### `universe_pool_registry`

One row per `chain + dex + pool`.

Required fields:

- `chain TEXT NOT NULL`
- `dex TEXT NOT NULL`
- `pool TEXT NOT NULL`
- `token0 TEXT`
- `token1 TEXT`
- `fee_tier INTEGER`
- `factory TEXT NOT NULL`
- `creation_block INTEGER NOT NULL`
- `creation_tx TEXT`
- `created_at TEXT`
- `discovery_branch TEXT NOT NULL` — EXISTING or NEW
- `first_seen_at TEXT NOT NULL`
- `last_seen_at TEXT NOT NULL`
- `market_state TEXT NOT NULL DEFAULT 'COLD'`
- `state_changed_at TEXT NOT NULL`
- `next_observation_at TEXT`
- `last_observation_at TEXT`
- `latest_liquidity_usd REAL`
- `latest_volume_24h REAL`
- `latest_price_usd REAL`
- `latest_txns_5m INTEGER`
- `latest_txns_1h INTEGER`
- `latest_txns_6h INTEGER`
- `latest_txns_24h INTEGER`
- `latest_change_5m REAL`
- `latest_change_1h REAL`
- `latest_change_6h REAL`
- `latest_change_24h REAL`
- `latest_snapshot_source TEXT`
- `latest_snapshot_at TEXT`
- `profile_json TEXT`

Primary key:

`PRIMARY KEY(chain, dex, pool)`

Constraints:

- `market_state IN ('COLD','WARM','HOT')`
- `discovery_branch IN ('EXISTING','NEW')`
- canonical lower-case EVM addresses at the application boundary
- no deletion caused by age, liquidity, volume, buys, FDV, WATCH, or REJECT

Indexes:

- `(market_state, next_observation_at)`
- `(dex, creation_block)`
- `(token0)`
- `(token1)`
- `(latest_snapshot_at)`

### `universe_discovery_checkpoint`

One row per factory/event stream.

Fields:

- `chain TEXT NOT NULL`
- `dex TEXT NOT NULL`
- `factory TEXT NOT NULL`
- `event_kind TEXT NOT NULL`
- `last_scanned_block INTEGER NOT NULL`
- `last_finalized_block INTEGER NOT NULL`
- `updated_at TEXT NOT NULL`

Primary key:

`PRIMARY KEY(chain, dex, factory, event_kind)`

Checkpoint advancement occurs in the same transaction as registry upserts for
the scanned range.

### Existing `market_observation_history`

The append-only raw fact table is preserved.

Its current source-isolated history remains valuable. New snapshot fields must
be added through an explicit ordered migration or a separate append-only
versioned observation table; silent semantic reuse of columns is prohibited.

Raw provider facts, derived seismic features, decisions, and labels remain
separate.

## 7. State transition contract

Initial state is COLD.

Transitions require real observation history:

- COLD -> WARM: meaningful measured movement/activity
- WARM -> HOT: stronger anomaly/acceleration evidence
- HOT -> WARM: anomaly subsides but observation remains active
- WARM -> COLD: sustained quiet behavior
- any state -> same state: normal refresh

Exact thresholds are not frozen in this document. They must be calibrated
from preserved BSC/Pancake history and represented as configuration with
provenance. No arbitrary threshold may be described as statistically learned.

Provider failure or insufficient history does not manufacture a promotion.

## 8. Existing component disposition

### Preserve

- `CandidateAdmissionQueue` strict boundedness, deduplication, cooldown and
  heap compaction
- append-only `market_observation_history`
- source-isolated stream math
- native WSS delivery/reorg/lifecycle correctness
- security hard veto and UNKNOWN semantics
- existing PAPER/VUR_KAC authority boundaries

### Change after the new path passes

- queue priority: seismic score/state first, then measured market profile;
  boundedness remains unchanged
- ingress: pool age becomes profile data, not `POOL_OUT_OF_SCOPE`
- cache terminology in `ConveyorLabeler`: replace COLD/WARM with unambiguous
  analyzer-cache HIT/PARTIAL/MISS terminology
- Gecko cache ownership: migrate canonical universe operations into
  `UniverseRegistry` while preserving compatible price/history consumers
- runtime composition: bind exactly one universe observation runtime

### Remove only after cutover PASS

- Gecko `/new_pools` as canonical discovery
- 48-hour hard universe exclusion
- analyzer-cache COLD/WARM terminology
- obsolete config, tests, imports and compatibility code proven unused

Old and new canonical discovery paths must not remain active side by side
after cutover.

## 9. Delivery order and gates

1. Registry schema + migration + idempotency tests
2. V2/V3 EXISTING/NEW discovery with resumable checkpoint tests
3. DexScreener official bounded batch snapshot client
4. raw observation persistence and due-work scheduler
5. seismic feature computation and state-transition tests
6. WARM/HOT queue priority integration
7. HOT deep-path integration
8. shadow observation acceptance
9. canonical cutover
10. legacy removal and full post-audit seal

Each unit follows:

`PLAN -> APPLY -> TARGETED TEST -> FULL REGRESSION -> POST_AUDIT -> GITHUB`

No risky next unit starts before the current unit passes.

## 10. First implementation acceptance

The initial registry core passes only when:

- clean database migration passes
- existing cache database migration passes
- repeated migration is idempotent
- identical EXISTING/NEW discovery collapses to one registry row
- checkpoint + registry transaction is atomic
- due reads are indexed and bounded by explicit limit
- age/liquidity do not delete or exclude registry rows
- COLD/WARM/HOT values are reserved exclusively for market state
- no HTTP, RPC, WSS, analyzer, AI, paper trade, wallet, signing, or live
  execution side effect exists
- existing full regression remains green
