# Coinoskobi Test Results

Bu dosya tamamlanan fazların tarihsel doğrulama sonuçlarını ve sonraki canonical maintenance acceptance kanıtlarını saklar. Eski test sayıları tarihsel baseline'dır; en güncel repository-wide sonuç en alttaki maintenance closure kaydında belirtilir.

## Historical Phase Closure Summary

- Phase 0–1 closure baseline: 36 passed
- Phase 2 closure baseline: 128 passed
- Phase 3 closure baseline: 198 passed
- Phase 4 closure baseline: 239 passed
- Phase 5 closure baseline: 253 passed
- Phase 0–7 quality seal: 396 passed
- Phase 8 native WSS validation: PASS
- Phase 9 wallet/entity validation: PASS
- Phase 10 adversary validation: PASS
- Phase 11 learning validation: PASS
- Phase 0–13 preflight baseline: 914 passed
- Phase 15 final roadmap closure: 966 passed
- Unified entry admission maintenance baseline: 1011 passed
- Risk/math maintenance baseline: 1005 passed

Historical detailed reports remain available in repository history and retained phase-scoped report files. These numbers must not be interpreted as the current collected-test count.

Known recurring non-blocking warning:
- dependency-owned `websockets.legacy` deprecation warning

---

# Canonical Provider Broker Maintenance — 2026-09-01

Status: **VALIDATED / MERGED**

Ownership:
- provider broker/resilience → Phase 8
- provider operability/quota budget → Phase 12
- counterfactual provider pressure → Phase 13

No Phase 16 / ERA / architecture V2/V3 opened.

## Functional Scope

Candidate branch: `phase13/provider-broker`

Functional commit after rebase:
`7abd0af74a0af3fbdcb74392332ca82d74ebc2b0`

CI gate commit:
`85c52daaab972684ff2f7775b8ae5d1ec5ba4797`

Implemented/validated contracts:
- canonical HTTP/WSS provider broker
- up to four optional provider slots
- duplicate URL collapse
- rate-limit/quota/403 failure classification
- circuit-breaker cooldown
- transient transport cooldown
- all-circuits-open fail-fast without another provider request
- heavy RPC routing across healthy providers
- bounded exact-request cache
- in-flight identical-request coalescing
- bounded primary-first WSS fallback
- status does not expose provider URLs/secrets
- decision authority = false
- paper authority = false
- live authority = false
- wallet authority = false
- execution authority = false

Removed obsolete provider contracts:
- `app/dex/wss_failover.py`
- `tests/test_provider_primary_secondary.py`
- `tests/test_provider_resilience.py`
- old `FailoverHTTPProvider`
- old `FailoverWSSRuntime`
- old `choose_provider`
- old `failover_allowed`

## Counterfactual Pressure Contract

Phase 13 counterfactual observation was bounded to:
- max 30 pending pools per scanner refresh
- one Gecko multi-pool request for the bounded fetch batch
- remaining rows deferred to later normal refreshes

## Local Acceptance

Before initial provider branch push:
- targeted provider/pressure/E2E: **24 passed / 0 failed**
- full repository regression: **1155 passed / 0 failed**
- runtime: **335.25 s**
- warning count: **1**

After rebase onto merged canonical main:
- targeted acceptance: **9 passed / 0 failed**
- warning count: **1**

Dead-code audit: **PASS**

Runtime restarted by validation: **FALSE**
Environment `.env` changed by validation: **FALSE**

## GitHub Acceptance

After `tests/test_provider_broker.py` was added to the canonical smoke gate:

- PR #61 pull_request run #462: **SUCCESS**
- push `[full]` run #461: **SUCCESS**

The push run used commit message:
`ci: gate provider broker in canonical smoke [full]`

Provider broker functional validation: **PASS**
Provider cleanup audit: **PASS**
Authority audit: **PASS**
GitHub smoke/E2E: **PASS**
GitHub full regression: **PASS**
Merge: **PASS**

---

# Phase 14 Vezir / Canonical Panel Final Maintenance Seal — 2026-09-04

Status: **VALIDATED**

Ownership:
- canonical Command Center / Vezir operator support → Phase 14

Relevant merged PRs:
- PR #79 — read-only Groq intent router + compact Vezir presentation
- PR #80 — GPT-OSS empty-output fix
- PR #96 — canonical panel acceptance + intelligence feed restoration
- PR #97 — final acceptance regression hotfix

PR #97 merge commit:
`aa7bbbeb8a6c8b55490ace5838191d57d5b0e4e2`

PR #97 scope audit:
- plural regulatory negative terms classified correctly
- Vezir learning test aligned with actual `WatchProbeStore` lifecycle
- no authority change
- no live/wallet/signing/execution change
- Codex review completed with no reported findings

## VPS Final Acceptance

Observed final diagnostic:
- targeted Vezir tests: **20 passed**
- real Groq router: **PASS**
- `AI_USED=True`
- provider: `GROQ`
- model: `openai/gpt-oss-120b`
- routed intent: `GENERAL`
- fallback reason: `None`
- router returned no direct answer field as designed: **PASS**
- canonical panel-only restart: **PASS**
- port 8098 readiness: **PASS**
- `/api/vezir/ask`: **PASS**
- endpoint answer present: **PASS**
- authority: `READ_ONLY`
- paper runtime untouched: **PASS**
- `PHASE14_VEZIR_GROQ_FINAL=PASS`

## Authority Seal

- AI trade authority = 0
- live execution authority = 0
- wallet authority = 0
- signing authority = 0
- runtime-control authority from Vezir = 0
- deployment authority from Vezir = 0

Final maintenance acceptance: **PASS**

---

# Paper Runtime / Integrity Maintenance Seal — 2026-09-16

Status: **VALIDATED WITH NATURAL NORMAL PAPER RUNTIME E2E PENDING**

## Repository-wide Regression

Validated on main SHA:
`768a3e30c9f6a8cc5054211209cbf18f9922f2e0`

Result:
- full repository suite: **1583 passed / 0 failed**
- warning count: **1**
- warning: dependency-owned `websockets.legacy` deprecation
- `PYTEST_RC=0`

The four stale regression expectations corrected before this run covered:
- canonical frontend asset version
- valid positive paper outcome position IDs
- current VUR_KAC full-exit invariant

## Timestamp Integrity Maintenance

PR #182 cleanly ported the remaining outcome timestamp-integrity work onto the current runtime/code baseline.

Runtime/code baseline after PR #182 merge, before documentation-only seal:
`81797953f2f06dd3604d8a6da63434fa1e79a9cc`

Validated contracts:
- canonical aware timestamp grammar accepted
- malformed timestamps rejected
- naive timestamps rejected
- malformed suffix/NUL rejected
- excessive fractional precision rejected
- invalid dates/times/offsets rejected
- outcome exclusion registry fails closed on invalid fingerprints
- stored invalid outcome fingerprints fail calibration closed
- invalid outcome fingerprints cannot bootstrap paper position sizing
- runtime learning uses the same timestamp integrity boundary

Final targeted suite on that runtime/code baseline:
- **51 passed / 0 failed**
- warning count: **1**
- direct validator check: **PASS**
- `py_compile`: PASS
- `git diff --check`: PASS before merge

## Runtime Smoke on Runtime/Code Baseline

Observed after deploying runtime/code baseline SHA `81797953f2f06dd3604d8a6da63434fa1e79a9cc`:
- `coinoskobi-paper-runtime.service`: **active**
- critical runtime error scan: **empty**
- `paper_trades.db` integrity: **ok**
- open positions: **0**
- last trade id: **39**

No recurrence observed in the final smoke for:
- `pool identity mapping required`
- counterfactual price refresh failure
- candidate observation price refresh failure
- traceback / critical / background cycle failure
- `OUTCOME_FINGERPRINT_INVALID`

## Real PAPER Runtime E2E Evidence

Trade id `39` is the first post-baseline real PAPER runtime trade in this maintenance sequence.

Observed durable state:
- control mode: `AUTO`
- trade type: `VUR_KAC`
- status: `CLOSED`
- close reason: `MATHEMATICAL_NO_UPSIDE_EXIT`
- entry amount: `43.0450136836645 USDT`
- realized PnL: `-4.14549262253072 USDT`
- net PnL: `-4.14549262253072 USDT`
- partial realization rows: `0`
- remaining cost basis: `0`
- remaining token amount: `0`
- TP1: `0`
- TP2: `0`
- runner: `0`

Accounting assertions:
- PnL identity: **PASS**
- net PnL match: **PASS**
- full exit: **PASS**

Therefore the real VUR_KAC PAPER runtime full-exit/accounting lifecycle is **runtime-proven**.

A natural `NORMAL` PAPER position has still not opened in the durable runtime database. NORMAL TP1 → TP2 → TP3/runner → close/accounting remains a pending natural runtime E2E observation and must not be forced by weakening risk, sizing, LP-withdrawal protection, sellability, admission, or hard-block rules.

## Pull Request Cleanup

- PR #145: closed as superseded by current fail-closed provider behavior
- PR #151: closed as superseded by PR #182 current-main port
- PR #181: merged — stale regression expectation cleanup
- PR #182: merged — outcome timestamp integrity

Documentation-only seal commits may move repository `main` beyond the verified runtime/code baseline without changing runtime behavior.

Final maintenance evidence seal: **PASS, with natural NORMAL PAPER runtime E2E explicitly pending**

---

# Phase 13D Forensic Learning Final Maintenance Closure — 2026-09-16

Status: **VALIDATED / MERGED / DEPLOYED / RUNTIME-SMOKE PASS**

Ownership:
- Phase 13D — Unified Outcome Calibration Readmodel maintenance
- no new Phase/ERA/version tree opened

## Pull Request / Merge

- PR #186: `Phase 13D: add bounded forensic outcome learning`
- final branch HEAD before merge: `fc0dead79ae7385337d95644a6336cf26be3dcfc`
- merge commit on `main`: `a75dd8d7bb4494da4934334a5829e4f3385e9e90`

## Final Validation

Exact final-branch verification before merge:
- targeted final suite: **33 passed / 0 failed**
- full repository regression: **1630 passed / 0 failed**
- full regression runtime: **414.31 s**
- warning count: **1**
- recurring warning: dependency-owned `websockets.legacy` deprecation

Earlier closure rounds also passed:
- review regressions: **51 passed / 0 failed**
- performance/risk: **15 passed / 0 failed**
- smoke/E2E: **288 passed / 0 failed**
- preceding full suite: **1627 passed / 0 failed**
- promotion-attribution targeted: **28 passed / 0 failed**
- promotion-attribution smoke/E2E: **53 passed / 0 failed**
- preceding full suite after promotion fix: **1629 passed / 0 failed**

## Validated Forensic Contracts

- bounded paper loss forensics
- confirmed profit-giveback only when peak evidence exists
- price-upside-given-back classification without inventing peak-net evidence
- gross-positive/net-negative cost-drag detection
- currency-aware lifecycle PnL; legacy BNB is not relabeled as USDT
- durable counterfactual 2x/5x/10x/100x/1000x missed-opportunity buckets
- blocker attribution from canonical decision context
- durable/RAM duplicate decision suppression by shared observation identity
- malformed forensic payload tolerance
- optional durable forensic history read is fail-open for runtime availability
- post-promotion threshold events excluded from missed-opportunity attribution
- post-promotion all-time `max_price` excluded from missed-opportunity example maxima
- bounded examples and no raw DB scan/provider call in the forensic readmodel

## Authority / Safety Seal

The closure preserves:
- proposal-only learning
- automatic threshold apply = false
- automatic config write = false
- strategy rewrite = false
- hard-safety weakening = false
- AI authority = false
- trade permission/authority = false
- paper authority from forensic readmodel = false
- live authority = false
- wallet authority = false
- signing authority = false
- execution authority = false

## External Review Closure

Review cycles used Codex, Strix, CodeRabbit and Copilot.

Material findings raised during review were fixed before merge, including:
- production durable-observation binding
- lifecycle evidence binding
- NEGATIVE/FALSE_NEGATIVE semantic preservation
- RAM/durable deduplication
- explicit authority-denial fields
- legacy-close fresh lifecycle values
- lifecycle evidence all-None coverage
- restart/replay legacy PnL preservation
- legacy BNB/USDT currency correctness
- optional durable read fail-open behavior
- malformed evidence handling
- pre-classified EXPECTED_LOSS exclusion from missed-opportunity fallback
- post-promotion missed-opportunity bucketing
- post-promotion example-max attribution

Review threads were resolved before final merge.

## Post-Merge VPS Runtime Smoke

Deployed merge SHA:
`a75dd8d7bb4494da4934334a5829e4f3385e9e90`

Observed after restart:
- `coinoskobi-paper-runtime.service`: **active (running)**
- wallet outcome hydration: `READY`
- SQLite `PRAGMA integrity_check`: **ok**
- clean application-owned shutdown/restart sequence observed
- runtime remained active and processing after restart
- `POST_MERGE_RUNTIME_SMOKE=PASS`

One non-blocking provider warning was observed:
- `DexScreener snapshot fallback unavailable: 'NoneType' object is not iterable`

This warning did not stop the service and is not part of the Phase 13D forensic-learning correctness boundary.

## Final Result

Phase 13D forensic-learning maintenance closure: **PASS**.

PR merged, production runtime deployed, final regression green, DB integrity green, runtime smoke green, review findings closed, and canonical evidence recorded.

Natural `NORMAL` PAPER TP1 → TP2 → TP3/runner lifecycle evidence remains a separate Phase 4/12 natural-runtime observation target and must not be forced by weakening safety or admission gates.

---

# Paper Price Evidence / VUR_KAC Admission Maintenance Closure — 2026-09-17

Status: **VALIDATED / MERGED / DEPLOYED / RUNTIME-SMOKE PASS**

Ownership:
- Phase 4 — position lifecycle / hot open-position handling
- Phase 12 — operational paper runtime / provider operability
- no new phase/ERA/version tree opened

## Pull Request / Merge

- PR #187: `Fix paper price evidence freshness and VUR_KAC admission`
- final branch HEAD before merge: `7d76d69e1b84d3b9f8c84eb803f26000e49e9ed0`
- merge commit on `main`: `3eaabe8c73c6b22bd0e0dd793afad02b07da5425`

## Functional Corrections

Validated contracts:
- paper sizing prefers the freshest sellability-local evidence over stale risk/risk-gate local evidence
- VUR_KAC one-bar rebound after a negative prior return is not admission-ready
- positive prior + latest continuation remains admission-ready when other evidence is valid
- deteriorating/unavailable liquidity prevents VUR_KAC promotion
- `updated_at` remains the market-quality/scanner timestamp
- dedicated `price_updated_at` tracks live/provider/WSS price freshness
- price-only refresh no longer makes stale liquidity/volume/buys/FDV appear fresh
- stale exact open-position prices fail closed
- stale open-position prices cannot fall through to token-cache fallback pricing
- stale cache prices cannot anchor WSS relative pricing
- no historical stop fill or exit is fabricated while price evidence is stale

## Validation Sequence

Initial targeted maintenance verification:
- **24 passed / 0 failed**
- warning count: **1**

First repository-wide regression exposed a timestamp contract conflict:
- **1633 passed / 1 failed**
- failing test: `tests/test_tracked_pool_price.py::test_price_only_refresh_preserves_market_quality_timestamp`
- observed issue: price-only refresh advanced shared `updated_at`
- correction: separate market-quality freshness from price freshness using `price_updated_at`

Final targeted verification after correction:
- **27 passed / 0 failed**
- warning count: **1**
- `git diff --check`: PASS

Final repository-wide regression:
- **1635 passed / 0 failed**
- warning count: **1**
- runtime: **441.18 s**
- recurring warning: dependency-owned `websockets.legacy` deprecation

## Review / CI Evidence

- CodeRabbit/Codex review identified the shared-timestamp P1 concern; the final implementation separated price freshness from market-quality freshness
- the stale review thread was resolved after the correction
- GitHub pull-request smoke jobs failed before any workflow step was created; therefore they were not treated as successful code-validation evidence
- this closure relies on the successful VPS targeted/full regression and post-deploy runtime smoke for acceptance

## Post-Merge VPS Runtime Smoke

Deployed merge SHA:
`3eaabe8c73c6b22bd0e0dd793afad02b07da5425`

Observed after restart:
- `coinoskobi-paper-runtime.service`: **active**
- post-restart PID: `3067324`
- independent runtime jobs: `paper_manager`, `paper_hot_manager`
- `gecko_pool_cache` schema includes both `updated_at` and `price_updated_at`
- recent cache rows contain current price freshness timestamps
- critical runtime scan found no traceback, SQLite thread error, database locked, fatal or critical condition
- scanner/fast-watch/pipeline processing continued after restart

Observed non-blocking provider warnings:
- `DexScreener snapshot fallback unavailable: 'NoneType' object is not iterable`
- Universe discovery `HTTPError`
- Universe discovery `ConnectionError`

These warnings did not stop the runtime and are outside this maintenance acceptance boundary.

## Final Result

Paper price evidence / VUR_KAC admission maintenance closure: **PASS**.

Targeted regression green, full repository regression green, PR merged, production runtime deployed, dedicated price freshness schema confirmed, runtime critical-error scan clean, and service active.

Natural `NORMAL` PAPER TP1 → TP2 → TP3/runner → close remains explicitly pending as a separate Phase 4/12 natural-runtime E2E observation and must not be forced by weakening admission, sizing, LP protection, sellability, risk, or hard-block gates.

## 2026-09-17 — Neutral quote flow semantics

Result: PASS

Code:
- app/strategy/unified_score.py

Regression coverage:
- tests/test_runtime_opportunity_price_history.py
- tests/test_unified_score.py

Targeted:
- 48 passed
- 1 warning

Full repository regression:
- 1637 passed
- 0 failed
- 1 warning
- 433.79 seconds

Post-deploy runtime:
- deployed SHA: 3b5bdd62b04b6b854dc04410457d86c7575905c7
- service active after restart
- new process produced 20 zero-flow observations
- NEUTRAL: 20
- OPPOSING: 0
- positive single-bar momentum remained WATCH when continuation was not established

Conclusion:
Zero measured quote-reserve change is no longer mislabeled as opposing flow.
Negative measured flow remains a veto.
Recovery breakout still requires positive flow.
## RESERVE_COLLAPSE_MAINTENANCE_SEAL_20260917

Validation:
- Initial reserve-collapse/rug targeted: 8 passed.
- Runtime evidence targeted: 11 passed.
- Existing exit / LP regression: 23 passed.
- Reserve-collapse + UnifiedScore targeted: 35 passed, 1 warning.
- Paper / LP regression: 43 passed, 1 warning.
- Full pytest: 1647 passed, 1 warning in 477.46s; RC=0.
- git diff --check: PASS.
- Exact candidate-60615 pool runtime smoke before merge: PASS.
- Exact-pool post-deploy smoke after merge: PASS.
- Historical reserve withdrawal fraction: > 0.999.
- Catastrophic reserve collapse classification: PASS.
- UnifiedScore result on catastrophic evidence: WATCH / CATASTROPHIC_RESERVE_COLLAPSE.
- Authority assertions: decision/paper/execution authority remain false in classifier evidence.
- Runtime service active after deployment.
- Post-deploy critical-error journal audit: PASS.

CI note:
- PR-head GitHub Actions run 35196980907: smoke=failure, full=skipped, no useful smoke steps exposed.
- CI is therefore NOT recorded as green.
- The full local pytest result above is the executable regression evidence.
## PAPER_10K_RESET_SEAL_20260917

Validation:
- accounting targeted: 41 passed, 1 warning
- accounting full suite: 1652 passed, 1 warning
- panel targeted: 13 passed, 1 warning
- final panel full suite: 1653 passed, 1 warning
- real DB accounting before panel merge: PASS
- panel active boundary: PASS
- final active run minimum trade id: 40
- starting capital: 10000.0 USDT
- available capital at reset: 10000.0 USDT
- current-run trades at reset: 0
- historical trades preserved: 39
- final post-deploy 10K audit: PASS
