# Coinoskobi Phase 0-13 Validation & Load-Benchmark Preflight Report

Date: 2026-08-15
Repository: `anketci54-coder/coinoskobi-dexbot`
Baseline commit: `62f7015` (`feat: close Phase 13 outcome learning and calibration`)

## Executive result

**PREFLIGHT: PASS**

This run validates repository/runtime health and confirms that the codebase has the bounded queue/scheduler/learning structures needed for a controlled Phase 0-13 load benchmark. It does **not** constitute a new 10/s, 1k/s, 10k/s or 100k/s end-to-end load simulation; those rates still require the dedicated isolated harness.

## Repository truth

- Local branch: `main`
- `HEAD` and `origin/main` were synchronized at `62f7015` before this documentation commit.
- Worktree was clean.
- Phase 13 is closed; Phase 14 was not started by the validation run.

## Host capacity

- CPU: 4 vCPU, AMD EPYC 9645
- RAM: 7.8 GiB total
- Available RAM during preflight: ~6.1 GiB
- Swap: none

## Production runtime health

Service: `coinoskobi-paper-runtime.service`

- ActiveState: `active`
- SubState: `running`
- MainPID: `472278`
- Restarts: `0`
- MemoryCurrent: ~101.6 MB
- MemoryPeak: ~102.9 MB
- Process RSS snapshot: ~113.8 MB
- CPU snapshot: ~0.3%
- Runtime error scan: `0`

Recent cycles remained `READY` and continued producing bounded paper/counterfactual learning evidence.

## Database safety and health

`data/paper_trades.db`

- Size: 425,984 bytes
- `PRAGMA integrity_check`: `ok`
- `PRAGMA quick_check`: `ok`
- SHA-256 before/after preflight identical: `747db06613d14303bb09514dbe4de0b523602c8656b01635d314275612a6fcab`

Conclusion: preflight did not modify the production paper DB.

## Phase 0-13 architecture evidence relevant to load

The repository exposes the real bounded ingress path through:

- `CandidateAdmissionQueue.enqueue()` / `enqueue_many()`
- `WorkScheduler.process_queue()`
- `PipelineEngine.run_cycle()`
- bounded candidate queue integration in `PipelineEngine`
- bounded learning/readmodel stores
- bounded counterfactual observation
- bounded runtime outcome feed

The source audit also confirms explicit no-RPC sections in normalization/conveyor/execution-context paths, while external/provider boundaries remain separately identifiable.

## Existing stress and boundedness evidence

Existing tests include pressure coverage at 1k, 10k and 100k scales, including:

- `tests/test_candidate_queue_boundedness.py`
- `tests/test_phase11_learning_stress.py`
- `tests/test_phase10_stress.py`
- `tests/test_phase9_stress.py`
- `tests/test_phase8_stress.py`
- `tests/test_ocr_bounded_soak.py`
- scheduler streaming/fairness/work-scheduler tests
- bounded runtime market-flow and actor-intelligence tests

This establishes boundedness evidence, but it must not be confused with a fresh full Phase 0-13 arrival-rate benchmark.

## Historical verified throughput baseline

The existing `TEST_RESULTS.md` Phase 2 scale validation records:

| Candidate batch | Historical result |
|---:|---:|
| 1,000 | ~6,532 candidates/s |
| 15,000 | ~6,338 candidates/s |
| 100,000 | ~6,440 candidates/s |

Historical 100k breakdown:

- enqueue: ~2.436 s
- scheduler: ~13.092 s
- total: ~15.528 s
- peak Python allocation: ~142.6 MB

These are historical Phase 2 benchmark numbers, not a new Phase 13 end-to-end measurement.

## Current Phase 13 regression evidence

Immediately preceding this preflight, the validated repository baseline reported:

- targeted Phase 13 regression: `17 passed`
- full regression: `914 passed`
- full regression runtime: `319.46 s`
- compile: PASS
- critical import smoke: PASS
- DB integrity/quick check: PASS
- production runtime error count: 0
- no service restart
- no production DB write by the validation procedure

Known non-blocking warning:

- dependency-owned `websockets.legacy` deprecation warning

## Runtime learning evidence

The live service continued reporting `unified=READY` with paper and counterfactual sample channels active. Observed counterfactual classes included `FALSE_NEGATIVE`, `MISSED_OPPORTUNITY`, `EXPECTED_LOSS`, and cumulative historical `AVOIDED_LOSS` evidence.

## Capacity interpretation

The machine has ample memory headroom at current production load. Historical local/synthetic scheduler throughput around 6.4k candidates/s suggests that 10/s and 1k/s are below the historical CPU-side pipeline throughput envelope. However, **10k/s and 100k/s sustained ingress cannot be claimed as supported from this preflight alone**. At those rates, queue admission/backpressure, analyzer mix, cache warmth, external I/O, provider limits, and Phase 13 observation cost must be measured with the dedicated isolated benchmark.

A burst of 100k candidates is also different from sustaining 100k candidates every second. Historical processing of a 100k batch in ~15.5 seconds corresponds to ~6.44k candidates/s for that earlier benchmark configuration; it does not prove 100k/s sustainable throughput.

## Safety boundary

This validation performed no service restart, no source-code deletion, no roadmap write, no production DB write, no provider/RPC benchmark traffic, no live/wallet/signing action, and no Phase 14 start.

## Final decision

**Phase 0-13 preflight health: PASS.**

**Fresh 10/s → 1k/s → 10k/s → 100k/s end-to-end benchmark: NOT YET EXECUTED.**

Next measurement should use an isolated harness bound to the repository's real ingress/queue/scheduler/Phase 13 observation path, with provider and production DB writes disabled, and should record throughput, enqueue latency, p50/p95/p99 processing latency, queue depth/backpressure/drop behavior, CPU, RSS/peak RAM, and Phase 13 observation overhead separately.
