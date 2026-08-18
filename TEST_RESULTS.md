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


## Phase 10 Final Validation — 2026-08-11

- Test collection: PASS
- Smoke: PASS
- End-to-end: PASS
- Phase 10 targeted: PASS
- Phase 0-10 connection regression: PASS
- Full regression: PASS
- Compile: PASS
- Phase 5-10 speed matrix: PASS
- Adversary hot-path benchmark: PASS
- Scheduler load: PASS
- Bounded structure stress: PASS
- Adversarial false-positive matrix: PASS
- DB integrity / quick check: PASS
- DB unchanged: PASS
- Generated-junk cleanup: PASS
- Authority / hot-path contract: PASS
- Phase 10: CLOSED
- Phase 11: CLOSED

## Phase 11 — Learning / Calibration / Outcome Memory

Status: CLOSED

Validation:

- Phase 0-10 closure repair: PASS
- 790-test collection baseline: PASS
- full regression: PASS
- runtime composition: PASS
- clean-start paper schema: PASS
- SQLite concurrency: PASS
- bounded operational WSS: PASS
- dependency reproducibility: PASS
- outcome evidence/classification: PASS
- signal attribution: PASS
- bounded outcome memory: PASS
- minimum-sample calibration guard: PASS
- proposal-only weight/threshold layer: PASS
- soft decay / hard evidence preservation: PASS
- learning hot-path readmodel: PASS
- anti-overfit / bias stress: PASS
- DB health: PASS
- authority / auto-apply zero: PASS

Phase 12 remains RESERVED.

---

# OCR Final Verified Results — 2026-08-12

Bu bölüm güncel kapanış baseline'ıdır.

Historical test sayıları (ör. 790 / 813 / 845 / 856 / 866)
önceki ara doğrulamalardır; güncel final baseline değildir.

## Final Regression

- Collected/executed final suite: 870 tests
- PASS: 870
- FAIL: 0
- ERROR: 0
- Warning: 1
- Warning classification:
  dependency-owned `websockets.legacy` deprecation warning via Web3
- Runtime: approximately 67 seconds

## Closure / Soak / E2E

- Selected closure suite: 26 PASS
- True composition-root E2E: PASS
- Runner lifecycle E2E: PASS
- Restart/recovery: PASS
- Bounded soak: PASS
- WSS lifecycle/reorg: PASS
- Multiprocess paper DB contention: PASS

## WSS Final Hardening

- Two-stage shutdown implemented:
  graceful stop → transport close → task cancellation
- Forced cancellation no longer leaks `CancelledError` as thread failure
- Targeted WSS suite: 27 PASS

## Database

- `data/cache/cache.db`
  - integrity_check: ok
  - quick_check: ok

- `data/paper_trades.db`
  - integrity_check: ok
  - quick_check: ok
  - schema version: v2
  - DB-level single OPEN invariant preserved

## Authority

Final authority audit:

- decision authority: zero
- live authority: zero
- wallet authority: zero
- execution authority: zero
- Phase 11 calibration remains proposal-only
- no auto weight/threshold/config apply

## Repository Hygiene

- generated cache/junk cleaned
- empty Dockerfile removed
- empty docker-compose.yml removed
- structural package `__init__.py` files preserved
- `.gitkeep` files preserved
- no patch/reject/backup residue found

## Final OCR State

OCR technical closure criteria are satisfied.

Independent adversarial re-audit:
- P0/BLOCKER: 0
- P1/HIGH: 0

Phase 12 remains RESERVED until explicit planning discussion.

---

# OCR Final Closure Results — 2026-08-13

- Full regression: 873 PASS
- Production-path E2E: PASS
- Restart/recovery: PASS
- WSS pair/token membership: PASS
- Paper schema v3 migration: PASS
- Opening-context persistence: PASS
- Paper close/replay learning path: PASS
- DB integrity / quick_check: PASS
- Authority audit: PASS
- Learning auto-apply: DISABLED
- OCR: CLOSED
- Phase 11: CLOSED
- Phase 12: RESERVED

---
Coinoskobi Phase 0-13 Validation & Load-Benchmark Preflight Report
Date: 2026-08-15 Repository: anketci54-coder/coinoskobi-dexbot Baseline commit: 62f7015 (feat: close Phase 13 outcome learning and calibration)

Executive result
PREFLIGHT: PASS

This run validates repository/runtime health and confirms that the codebase has the bounded queue/scheduler/learning structures needed for a controlled Phase 0-13 load benchmark. It does not constitute a new 10/s, 1k/s, 10k/s or 100k/s end-to-end load simulation; those rates still require the dedicated isolated harness.

Repository truth
Local branch: main
HEAD and origin/main were synchronized at 62f7015 before this documentation commit.
Worktree was clean.
Phase 13 is closed; Phase 14 was not started by the validation run.
Host capacity
CPU: 4 vCPU, AMD EPYC 9645
RAM: 7.8 GiB total
Available RAM during preflight: ~6.1 GiB
Swap: none
Production runtime health
Service: coinoskobi-paper-runtime.service

ActiveState: active
SubState: running
MainPID: 472278
Restarts: 0
MemoryCurrent: ~101.6 MB
MemoryPeak: ~102.9 MB
Process RSS snapshot: ~113.8 MB
CPU snapshot: ~0.3%
Runtime error scan: 0
Recent cycles remained READY and continued producing bounded paper/counterfactual learning evidence.

Database safety and health
data/paper_trades.db

Size: 425,984 bytes
PRAGMA integrity_check: ok
PRAGMA quick_check: ok
SHA-256 before/after preflight identical: 747db06613d14303bb09514dbe4de0b523602c8656b01635d314275612a6fcab
Conclusion: preflight did not modify the production paper DB.

Phase 0-13 architecture evidence relevant to load
The repository exposes the real bounded ingress path through:

CandidateAdmissionQueue.enqueue() / enqueue_many()
WorkScheduler.process_queue()
PipelineEngine.run_cycle()
bounded candidate queue integration in PipelineEngine
bounded learning/readmodel stores
bounded counterfactual observation
bounded runtime outcome feed
The source audit also confirms explicit no-RPC sections in normalization/conveyor/execution-context paths, while external/provider boundaries remain separately identifiable.

Existing stress and boundedness evidence
Existing tests include pressure coverage at 1k, 10k and 100k scales, including:

tests/test_candidate_queue_boundedness.py
tests/test_phase11_learning_stress.py
tests/test_phase10_stress.py
tests/test_phase9_stress.py
tests/test_phase8_stress.py
tests/test_ocr_bounded_soak.py
scheduler streaming/fairness/work-scheduler tests
bounded runtime market-flow and actor-intelligence tests
This establishes boundedness evidence, but it must not be confused with a fresh full Phase 0-13 arrival-rate benchmark.

Historical verified throughput baseline
The existing TEST_RESULTS.md Phase 2 scale validation records:

Candidate batch	Historical result
1,000	~6,532 candidates/s
15,000	~6,338 candidates/s
100,000	~6,440 candidates/s
Historical 100k breakdown:

enqueue: ~2.436 s
scheduler: ~13.092 s
total: ~15.528 s
peak Python allocation: ~142.6 MB
These are historical Phase 2 benchmark numbers, not a new Phase 13 end-to-end measurement.

Current Phase 13 regression evidence
Immediately preceding this preflight, the validated repository baseline reported:

targeted Phase 13 regression: 17 passed
full regression: 914 passed
full regression runtime: 319.46 s
compile: PASS
critical import smoke: PASS
DB integrity/quick check: PASS
production runtime error count: 0
no service restart
no production DB write by the validation procedure
Known non-blocking warning:

dependency-owned websockets.legacy deprecation warning
Runtime learning evidence
The live service continued reporting unified=READY with paper and counterfactual sample channels active. Observed counterfactual classes included FALSE_NEGATIVE, MISSED_OPPORTUNITY, EXPECTED_LOSS, and cumulative historical AVOIDED_LOSS evidence.

Capacity interpretation
The machine has ample memory headroom at current production load. Historical local/synthetic scheduler throughput around 6.4k candidates/s suggests that 10/s and 1k/s are below the historical CPU-side pipeline throughput envelope. However, 10k/s and 100k/s sustained ingress cannot be claimed as supported from this preflight alone. At those rates, queue admission/backpressure, analyzer mix, cache warmth, external I/O, provider limits, and Phase 13 observation cost must be measured with the dedicated isolated benchmark.

A burst of 100k candidates is also different from sustaining 100k candidates every second. Historical processing of a 100k batch in ~15.5 seconds corresponds to ~6.44k candidates/s for that earlier benchmark configuration; it does not prove 100k/s sustainable throughput.

Safety boundary
This validation performed no service restart, no source-code deletion, no roadmap write, no production DB write, no provider/RPC benchmark traffic, no live/wallet/signing action, and no Phase 14 start.

Final decision
Phase 0-13 preflight health: PASS.

Fresh 10/s → 1k/s → 10k/s → 100k/s end-to-end benchmark: NOT YET EXECUTED.

Next measurement should use an isolated harness bound to the repository's real ingress/queue/scheduler/Phase 13 observation path, with provider and production DB writes disabled, and should record throughput, enqueue latency, p50/p95/p99 processing latency, queue depth/backpressure/drop behavior, CPU, RSS/peak RAM, and Phase 13 observation overhead separately.

# Phase 15 Final End-to-End Validation — 2026-08-16

Status: ✅ PASS / CLOSED

## Environment

- Branch: `main`
- Validated HEAD: `77bf54ff07aa9e46a1e546b1685b07b94b821bba`
- Python: 3.13.5
- Repository worktree: clean

## Final Validation

- Test collection: 966
- Full regression: 966 passed / 0 failed
- Root E2E: 21 passed
- Application/runtime: 16 passed
- Paper/learning: 28 passed
- Risk/safety: 33 passed
- Phase 14 + Phase 15 contract: 47 passed

## Active Database

- `data/paper_trades.db`
- integrity_check: `ok`
- quick_check: `ok`
- foreign-key errors: `0`

## Safety Boundary

- Production code changed by validation: FALSE
- DB write by validation: FALSE
- Documentation write by validation: FALSE
- Network call by audit: FALSE
- Commit by validation: FALSE
- Push by validation: FALSE
- Phase 16 opened: FALSE

## Known Non-Blocking Warning

- dependency-owned `websockets.legacy` deprecation warning

## Final Gate

`PASS_PHASE15_END_TO_END_VALIDATION`

`FULL_SYSTEM_VALIDATION=PASS`

Phase 15: CLOSED.

Numbered roadmap Phase 0–15: COMPLETE.

Phase 16 / Era / V2 / V3: NOT AUTOMATICALLY OPENED.

---
## Post-Roadmap Full Regression — Unified Entry Admission Integration

Current synchronized baseline:

- Branch: `main`
- Commit: `6ef4c57`
- Commit title: `Complete unified entry admission integration`
- Full pytest result: **1011 passed / 0 failed**
- Warning count: **1**
- Warning: upstream `websockets.legacy` deprecation warning
- Python compile: **PASS**
- Git synchronization: **PASS**
- Final worktree: **CLEAN**

Validation performed after the final unified entry-admission integration:

- full repository pytest suite completed successfully
- all 1011 collected tests passed
- no failed tests
- local and `origin/main` resolved to the same commit
- cache cleanup completed
- Python compile completed successfully
- no residual tracked worktree changes remained

Entry-admission semantic validation established:

- hard block => REJECT
- confirmed safe sellability + final unified candidate => PAPER_BUY
- sellability UNKNOWN => REQUIRE_MORE_EVIDENCE
- provider/network sellability failure is not treated as conviction
- confirmed honeypot/unsellable evidence hard-blocks admission
- WATCH remains WATCH
- REJECT remains REJECT
- Stage-1 grants no paper/live/execution authority
- wallet/signing/execution authority remains false

The earlier **966 passed / 0 failed** result remains the historical Phase 15
roadmap-closure regression. It is not the current repository-wide regression
count.
