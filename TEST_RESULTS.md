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
