# Coinoskobi Test Results

Bu dosya tamamlanan fazların doğrulanmış test sonuçlarını saklar.

---

# Phase 0 — Critical Bug Fixes

Status: ✅ PASS / CLOSED

## Functional Tests

- Import Test ✅
- Compile Test ✅
- Scanner Test ✅
- Cache Filter Test ✅
- Gecko cache → filter field contract ✅
- Cache freshness filter ✅
- Pool age filter ✅
- MAX_RPC_CANDIDATES limit ✅
- Malformed cache row isolation ✅
- Token analyzer metadata ✅
- Pair analyzer integration ✅
- Risk analyzer integration ✅

## Fail-Safe Tests

- Invalid token address fail-safe ✅
- Token contract creation failure fail-safe ✅
- Pair RPC failure fail-safe ✅
- Risk RPC failure fail-safe ✅
- Missing risk data does not receive safe score ✅
- UNKNOWN analyzer state does not create false confidence ✅

## Cleanup Verification

- Legacy scanner files removed ✅
- Duplicate portfolio audit ✅
- Unused requirements removed ✅
- Temporary/debug/profile files audit ✅
- Patch/diff/backup files audit ✅

---

# Phase 1 — Core Infrastructure

Status: ✅ PASS / CLOSED

## Pipeline Tests

- Pipeline Smoke ✅
- Pipeline E2E ✅
- Real pair analyzer result binding ✅
- Analyzer health status propagation ✅
- TOKEN_OK / TOKEN_UNKNOWN ✅
- PAIR_OK / PAIR_UNKNOWN ✅
- RISK_OK / RISK_UNKNOWN ✅
- Single-token exception isolation ✅
- Cycle continues after candidate failure ✅
- Paper manager exception isolation ✅

## Core Infrastructure

- Runner ✅
- Scheduler import ✅
- Paper Database ✅
- SQLite WAL ✅
- Foreign Keys ✅
- Singleton ✅
- Paper manager/database API contract ✅
- Paper position update ✅
- Take Profit close ✅
- Stop Loss close ✅
- Trailing Stop close ✅
- Portfolio module import ✅

## Database Health

paper_trades.db:

- PRAGMA integrity_check = ok ✅
- PRAGMA quick_check = ok ✅
- paper_trades table available ✅

cache.db:

- PRAGMA integrity_check = ok ✅
- PRAGMA quick_check = ok ✅
- gecko_pool_cache available ✅
- erc20_cache available ✅
- pair_cache available ✅
- bytecode_cache available ✅

---

# Phase 0 + Phase 1 Final Closure Audit

## Main Environment

- Python 3.13 ✅
- Compile PASS ✅
- Import Smoke PASS ✅
- Core Smoke PASS ✅
- Full Pytest: 36/36 PASS ✅

## Clean Environment Verification

Fresh temporary virtual environment created only from `requirements.txt`.

- Dependency installation PASS ✅
- Project imports PASS ✅
- Full Pytest: 36/36 PASS ✅

This verifies that the repository does not depend on undeclared packages from the development virtual environment.

## Repository Audit

- Dead legacy files audit PASS ✅
- Exact duplicate audit PASS ✅
- Patch files: none ✅
- Diff files: none ✅
- Backup files: none ✅
- Temporary files: none ✅
- Debug files: none ✅
- Profile/benchmark leftovers: none ✅
- Generated Python cache cleaned ✅
- Git working tree clean at closure ✅

## Final Phase 0 / Phase 1 Result

PHASE 0: ✅ CLOSED

PHASE 1: ✅ CLOSED

Final verified test baseline:

**36 passed / 0 failed**

Known non-blocking warning:

- `websockets.legacy` deprecation warning from Web3 dependency stack.

This warning does not affect current test success or application correctness.

---

# Phase 2 — Performance & Scalable Pipeline Core

Status: ✅ PASS / CLOSED

Closure date: 2026-08-10

## Architecture Validation

- Ingress Gate DROP / DEFER / ACTIVE ✅
- Candidate Admission Queue ✅
- Duplicate collapse ✅
- Analyzer cache reuse ✅
- SQLite WAL analyzer cache ✅
- Conveyor WARM / PARTIAL / COLD ✅
- Common Candidate Model ✅
- Chain-aware token identity ✅
- Chain-aware pool identity ✅
- Chain-aware queue identity ✅
- Chain-aware analyzer cache identity ✅
- Network registry ✅
- DEX registry ✅
- Source adapter registry ✅
- GeckoTerminal BSC normalization ✅
- Second-network mock isolation ✅
- Continuous bounded scheduler ✅
- Legacy fixed candidate admission removed ✅
- Cost-aware scheduling ✅
- Multi-network round-robin fairness ✅
- Bounded HTTP 429 backoff ✅
- Paper / portfolio performance audit ✅

## Analyzer Performance

Measured baseline:

- Combined cold analyzer chain ≈ 537 ms
- Combined warm analyzer chain ≈ 0.17 ms

Conclusion:

- CPU-side ingress/filter was not the main bottleneck.
- Cold RPC / external I/O was the dominant cost.
- Cache reuse materially reduces repeated RPC cost.

## HTTP / Scanner Validation

GeckoTerminal observations:

- Successful public HTTP calls generally measured in tens of milliseconds.
- Public rate limiting returned HTTP 429 during aggressive benchmark polling.
- Normal runtime scanner cadence remains 300 seconds.
- `requests` remains sufficient for current runtime.
- aiohttp/async HTTP rewrite was not justified by measured need.
- Bounded 429 retry/backoff implemented.
- Scanner unit tests remain offline.
- Live smoke remains separate.

Final live smoke:

- RAW_ROWS = 20
- NORMALIZED = 20
- REJECTED = 0
- LIVE_SMOKE_MS ≈ 87.3 ms

## Final Scale Validation

### 1,000 candidates

- Processed: 1,000
- Failed: 0
- Pending: 0
- WARM: 700
- PARTIAL: 200
- COLD: 100
- BSC: 980
- Second mock network: 20
- Throughput ≈ 6,532 candidate/sec
- Peak Python allocation ≈ 1.41 MB

### 15,000 candidates

- Processed: 15,000
- Failed: 0
- Pending: 0
- WARM: 10,500
- PARTIAL: 3,000
- COLD: 1,500
- BSC: 14,700
- Second mock network: 300
- Throughput ≈ 6,338 candidate/sec
- Peak Python allocation ≈ 21.0 MB

### 100,000 candidates

- Processed: 100,000
- Failed: 0
- Pending: 0
- WARM: 70,000
- PARTIAL: 20,000
- COLD: 10,000
- BSC: 98,000
- Second mock network: 2,000
- Enqueue ≈ 2.436 sec
- Scheduler ≈ 13.092 sec
- Total ≈ 15.528 sec
- Throughput ≈ 6,440 candidate/sec
- Peak Python allocation ≈ 142.6 MB

## Duplicate / Identity Validation

Duplicate storm:

- Input events: 10,000
- Unique pending: 100
- Duplicates collapsed: 9,900

Chain-aware identity:

- Same token address on BSC and mock network remains two independent candidates ✅

Legacy architecture audit:

- `MAX_RPC_CANDIDATES` absent ✅
- legacy `pop_many()` admission path absent ✅

## Multi-Network Fairness

Validation:

- 1,000 BSC + 10 second-network candidates processed ✅
- Second network entered scheduling immediately ✅
- No starvation ✅
- Single active network can consume available worker capacity ✅
- Unused capacity is not reserved unnecessarily ✅
- WARM/PARTIAL/COLD cost priority preserved ✅

## Paper / Portfolio Audit

- Targeted paper tests: 3/3 PASS
- PaperManager process ≈ 0.82 ms
- No material paper-performance bottleneck found
- No large manager refactor justified
- Existing SQLite singleton/WAL behavior preserved

Observed non-blocking condition:

- Existing open position may log `Cache fiyatı bulunamadı` when no current cache price exists.
- This is a data-availability condition, not a Phase 2 performance failure.

## Database Health

`data/cache/cache.db`

- journal_mode = WAL ✅
- integrity_check = ok ✅
- quick_check = ok ✅

`data/paper_trades.db`

- journal_mode = WAL ✅
- integrity_check = ok ✅
- quick_check = ok ✅

## Final Regression

- Targeted Phase 2 regression: 68 passed / 0 failed ✅
- Full repository regression: 128 passed / 0 failed ✅
- Compile PASS ✅
- Import Smoke PASS ✅

Known non-blocking warning:

- `websockets.legacy` deprecation warning from dependency stack.

## Repository Cleanup Audit

- Untracked Phase 0–2 benchmark scripts: none ✅
- Tracked obsolete Phase 0–2 benchmark scripts: none ✅
- Backup / old / copy files: none ✅
- Extra script directories: none ✅
- All 25 test files are actively collected by pytest ✅
- Pipeline E2E tests remain active regression contracts ✅
- Smoke DB test remains active regression contract ✅
- Generated Python / pytest caches cleaned ✅

## Final Phase 2 Result

**PHASE 2: ✅ CLOSED**

Final verified baseline:

**128 passed / 0 failed**

Next roadmap phase:

**PHASE 3 — Strategy**

---

# Phase 3 — Risk, Opportunity & Entry Feasibility

Status: ✅ PASS / CLOSED

Closure date: 2026-08-11

## Risk Architecture

- Config-driven strategy thresholds ✅
- Honeypot / sellability RiskGate ✅
- Confirmed critical risk hard-block ✅
- UNKNOWN != RISK ✅
- Suspicion != HARD_BLOCK ✅
- Bounded sellability deep-check ✅
- Trap / tax / transfer-control signals ✅
- MEV / sandwich exposure classification ✅
- Market context binding ✅

## Unified Score

- Unified Score v1 ✅
- Legacy strategy normalized to 0–100 ✅
- Tax penalty independent ✅
- MEV penalty independent ✅
- No duplicate contract-risk penalty ✅
- UNKNOWN evidence lowers confidence only ✅
- Hard-block cannot be overridden by high score ✅

## Unified Decision Contract

Decision interpretation:

- HARD_BLOCK → REJECT
- Score >= 90 + Confidence >= 80 → PAPER_BUY_CANDIDATE
- Score >= 90 + Confidence < 80 → REQUIRE_MORE_EVIDENCE
- 70 <= Score < 90 → WATCH
- Score < 70 → REJECT

Authority:

- decision_authority = false ✅
- paper_authority = false ✅
- live_authority = false ✅
- wallet_authority = false ✅
- execution_authority = false ✅

## Execution Cost / Entry Feasibility

Cost model:

Known Total Cost % =
Buy Tax
+ Sell Tax
+ Swap Fee
+ Slippage
+ MEV Cost
+ Gas %

Net Edge % =
Expected Gross Edge %
- Known Total Cost %

Rules:

- Missing execution cost remains UNKNOWN ✅
- Missing gas does not become zero ✅
- Missing swap fee does not become zero ✅
- Gas units are not interpreted as USD ✅
- No default-cost injection into feasibility ✅
- Pure-local calculation ✅

## Final Phase 3 Audit

- Targeted Phase 3 tests: 83 passed / 0 failed ✅
- Full repository tests: 198 passed / 0 failed ✅
- Compile PASS ✅
- Config duplicate audit PASS ✅
- Sellability config single copy ✅
- Honeypot URL single copy ✅
- MEV config single copy ✅
- Unified decision config single copy ✅
- No live / wallet execution surface detected ✅

Known non-blocking warning:

- `websockets.legacy` dependency deprecation warning

## Phase Boundary

Phase 3 answers:

**"Bu adaya girmek mantıklı mı?"**

Deferred to Phase 4:

- Multi-stage TP
- Runner position
- Trend-following SL
- Adaptive trailing
- DEX swap-flow momentum
- Volume quality
- Unique buyers / sellers
- Liquidity / reserve dynamics
- Momentum exhaustion
- Runner exit intelligence
- Position lifecycle management

## Final Phase 3 Result

**PHASE 3: ✅ CLOSED**

Next:

**PHASE 4 — Position Lifecycle / DEX Exit Intelligence**

---

# Phase 4 — Position Lifecycle Mechanical Core

Status: ✅ PASS / CLOSED

Closure date: 2026-08-11

Validation:

- Phase 4 targeted: 41/41 PASS
- Phase 0-4 connection regression: 183/183 PASS
- Full repository regression: 239/239 PASS
- Compile PASS
- DB integrity / quick_check PASS
- Lifecycle speed ≈ 51,329 ops/sec

Mechanical contract:

- TP1 closes 20%
- TP2 closes 25%
- TP3 closes 25%
- Runner retains 30%
- State progression is deterministic
- Duplicate TP blocked
- TP skipping blocked
- Remaining + realized fraction conserved
- Trailing stop is monotonic
- Runner has no mandatory fixed final TP

Runtime boundary:

- Phase 4 runtime binding: NONE
- Existing PaperManager behavior unchanged
- No live/wallet/execution authority added

Next:

**PHASE 5 — DEX Market Intelligence**

---


## Phase 5 Final Validation — 2026-08-11

- Real GeckoTerminal bounded read: PASS
- Real rows: 20
- Phase 5 targeted: 14/14 PASS
- Phase 0-5 connection regression: 95/95 PASS
- Full regression: 253/253 PASS
- Compile: PASS
- Cache DB unchanged: PASS
- Paper DB unchanged: PASS
- DB integrity/quick check: PASS
- Paper/live/wallet/signing: OFF
- Native Swap/Sync continuous stream validation: NOT YET CLAIMED
- Final result: PHASE 5 CLOSED / VERIFIED


## Phase 0-7 Final Quality Seal — 2026-08-11

- Test collection: PASS
- Smoke: PASS
- End-to-end: PASS
- Phase 5-7 connection: PASS
- Full regression: 396 PASS
- Compile: PASS
- Market Quality speed: PASS
- Phase 6 Exit speed: PASS
- Phase 7 Flow speed: PASS
- Scheduler speed: PASS
- DB integrity / quick check: PASS
- Generated-junk cleanup: PASS
- Phase 7: CLOSED
- Phase 8: PLANNING


## Phase 8 Final Validation — 2026-08-11

- Real bounded BSC WSS Swap/Sync: PASS
- Smoke: PASS
- End-to-end: PASS
- Phase 8 targeted: PASS
- Phase 0-8 connection: PASS
- Full regression: PASS
- Compile: PASS
- Throughput: PASS
- Bounded-memory stress: PASS
- DB integrity / quick check: PASS
- Cleanup: PASS
- Authority audit: PASS
- Phase 8: CLOSED
- Phase 9: RESERVED


## Phase 9 Final Validation — 2026-08-11

- Smoke: PASS
- End-to-end: PASS
- Phase 9 targeted: PASS
- Phase 0-9 connection regression: PASS
- Full regression: PASS
- Compile: PASS
- Wallet hot-path benchmark: PASS
- Bounded readmodel/cache stress: PASS
- False-attribution matrix: PASS
- DB integrity / quick check: PASS
- DB unchanged: PASS
- Generated-junk cleanup: PASS
- Authority / hot-path contract: PASS
- Phase 9: CLOSED
- Phase 10: RESERVED
