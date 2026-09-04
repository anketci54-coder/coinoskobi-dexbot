# COINOSKOBI CANONICAL PROJECT STATE

Updated: 2026-09-04

## CANONICAL SOURCE

- Repository: `anketci54-coder/coinoskobi-dexbot`
- Production branch: `main`
- Verified main SHA: `aa7bbbeb8a6c8b55490ace5838191d57d5b0e4e2`
- VPS project: `/root/projects/coinoskobi-dexbot`
- Main application: `main.py`
- Canonical panel application: `app.api.panel:app`
- Canonical backend: `app/api/panel.py`
- Canonical frontend: `app/api/static/index.html`
- Paper DB: `data/paper_trades.db`
- Cache/universe DB: `data/cache/cache.db`
- Paper runtime: `coinoskobi-paper-runtime.service`
- Panel runtime: `coinoskobi-panel-api.service`
- Panel port: `8098`

Repository, VPS working tree, runtime services and runtime databases together form production truth. Current SHA must be verified directly before any apply/restart.

## GOVERNANCE

- Only canonical architecture classification: **PHASE 0–15**.
- Phase 0–15 are CLOSED; Phase 15 is the final roadmap phase.
- No Phase 16, ERA, architecture V2/V3, OCR/R-number, post-roadmap or parallel roadmap chain.
- Maintenance is assigned to an existing Phase 0–15 owner.
- No side/test panel architecture and no fake runtime/panel data.
- Missing evidence remains `UNKNOWN`.
- AI trade authority = 0.
- Live execution authority = 0.
- Wallet/signing authority = 0.
- Paper execution remains isolated from live execution.
- Hot path remains fast/bounded; heavy provider work remains bounded slow-path/worker work.

## CURRENT PRODUCTION SCOPE

Production focus: **BNB Chain (BSC) + PancakeSwap**.

Identity:
- token = chain-aware address
- pool = chain + dex + pool
- readable names are display metadata only
- universe size is dynamic

External roles:
- RPC/WSS: on-chain truth/native events through canonical provider broker
- GeckoTerminal: discovery and bounded indexed market evidence
- DexScreener: bounded market snapshots/display metadata
- GoPlus/Honeypot.is: sellability/security evidence

Provider failure or missing evidence is never converted into safe evidence.

## PROVIDER ARCHITECTURE CHECKPOINT

Provider broker consolidation PR #61 was merged on 2026-09-01.
Merge commit: `5505900f81261d8216926eb2f40381ffd3f11969`.

Provider maintenance belongs to Phase 8; runtime operability/quota budget belongs to Phase 12; bounded counterfactual provider pressure belongs to Phase 13.

Canonical code boundaries:
- `app/chains/bsc.py` — BSC Web3 composition
- `app/dex/provider_broker.py` — HTTP/WSS broker
- `app/dex/provider_resilience.py` — failure classification/policy
- `app/dex/wss_service.py` — application WSS lifecycle

Broker contract:
- PRIMARY / SECONDARY / TERTIARY / QUATERNARY optional provider slots
- duplicate configured URLs collapsed
- heavy RPC methods distributed across healthy providers
- rate-limit/quota/403 circuit cooldown
- transient transport cooldown
- all-circuits-open fail-fast
- bounded exact-request cache and in-flight coalescing
- bounded primary-first WSS fallback
- no provider URL/secret exposure in status
- decision/paper/live/wallet/execution authority all false

## COUNTERFACTUAL PRESSURE BOUND

Phase 13 bounded observation contract:
- pending counterfactual Gecko fetch: max 30 pools per scanner refresh
- one bounded multi-pool request for that batch
- remaining pending observations wait for later normal refreshes

## PHASE 14 VEZIR CHECKPOINT

Vezir/Groq operator support remains Phase 14 maintenance.

Merged changes:
- PR #79 — read-only Groq intent router + compact Vezir presentation
- PR #80 — GPT-OSS empty-output fix
- PR #96 — canonical panel acceptance + intelligence feed restoration
- PR #97 — final acceptance regression hotfix

Current contract:
- provider output never becomes displayed operational truth
- Groq only routes into allowlisted deterministic intents
- displayed answer remains deterministic
- authority = `READ_ONLY`
- trade/wallet/signing/database-write/runtime-control/deployment permissions remain false
- technical detail is shown only when locally requested
- GPT-OSS router uses bounded completion and low reasoning effort

VPS final acceptance on 2026-09-04:
- targeted Vezir tests: **20 passed**
- real Groq router: PASS
- AI provider/model routing: PASS
- `/api/vezir/ask`: PASS
- answer field present at endpoint: PASS
- authority: READ_ONLY
- canonical panel port 8098 readiness after panel-only restart: PASS
- paper runtime untouched: PASS
- `PHASE14_VEZIR_GROQ_FINAL=PASS`

## PHASE OWNERSHIP CHECKPOINT

- Phase 0 — critical fixes/cleanup
- Phase 1 — core infrastructure/DB/recovery
- Phase 2 — bounded pipeline/universe/discovery
- Phase 3 — risk/sellability/entry feasibility
- Phase 4 — position lifecycle
- Phase 5 — DEX market intelligence
- Phase 6 — exit intelligence
- Phase 7 — flow/regime/seismic state
- Phase 8 — native ingestion/provider broker/resilience
- Phase 9 — wallet/entity/smart-money/whale intelligence
- Phase 10 — adversary/scam/MEV intelligence
- Phase 11 — learning/calibration/outcome memory
- Phase 12 — operational paper runtime/provider operability/E2E
- Phase 13 — paper/counterfactual calibration and bounded observation pressure
- Phase 14 — canonical Command Center/AI operator support
- Phase 15 — final operational validation/explicit-approval micro-live boundary

## NEXT MAINTENANCE TARGETS

All remain inside existing Phase 0–15:
- bounded Vezir conversation context → Phase 14
- successful-wallet tracking → Phase 9
- whale tracking → Phase 9
- news/market intelligence → Phase 5/7
- security hardening → Phase 1/3/10 according to concern

No new phase/era/version tree is permitted.

## RUNTIME RULE

- Documentation-only maintenance does not require runtime restart.
- Panel-only changes restart only `coinoskobi-panel-api.service` after tests.
- Paper runtime is not restarted for panel/documentation maintenance.
- Provider env/runtime changes require separate explicit operational need.
- Live/wallet/signing authority remains locked unless separately and explicitly approved.

## CANONICAL DOCUMENTS

- `README.md` — stable project contract
- `ROADMAP.md` — Phase 0–15 ownership map
- `PROJECT_STATE.md` — current continuation checkpoint
- `TEST_RESULTS.md` — historical validation evidence

Historical reports remain evidence, not active architecture.
