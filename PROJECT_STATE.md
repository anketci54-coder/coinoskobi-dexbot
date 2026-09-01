# COINOSKOBI CANONICAL PROJECT STATE

Updated: 2026-09-01

## CANONICAL SOURCE

- Repository: `anketci54-coder/coinoskobi-dexbot`
- Production branch: `main`
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
- Phase 0–15 are CLOSED; Phase 15 is final roadmap phase.
- No Phase 16, ERA, architecture V2/V3, OCR/R-number, post-roadmap or parallel roadmap chain.
- PancakeSwap V2/V3 remains valid only as actual DEX protocol naming.
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

## CANONICAL PROVIDER ARCHITECTURE

Provider maintenance belongs to existing **Phase 8**; runtime operability/quota budget belongs to **Phase 12**; bounded counterfactual provider pressure belongs to **Phase 13**.

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
- all-circuits-open fail-fast without another provider request
- bounded exact-request cache and in-flight coalescing
- bounded primary-first WSS fallback
- no provider URL/secret exposure in broker status
- decision/paper/live/wallet/execution authority all false

Legacy parallel `FailoverHTTPProvider`, `FailoverWSSRuntime`, `choose_provider` and `failover_allowed` contracts are removed from the candidate branch.

## ACTIVE INTEGRATION CANDIDATE — PR #61

Branch: `phase13/provider-broker`

Purpose: consolidate provider resilience and quota protection without opening a new architecture tree.

Functional provider commit after rebase:
`7abd0af74a0af3fbdcb74392332ca82d74ebc2b0`

CI gate commit:
`85c52daaab972684ff2f7775b8ae5d1ec5ba4797`

Validated evidence before documentation sync:
- local targeted provider/pressure/E2E: **24 passed**
- local full regression: **1155 passed / 0 failed**
- post-rebase targeted acceptance: **9 passed / 0 failed**
- dead-code audit: PASS
- GitHub PR smoke/E2E run #462: SUCCESS
- GitHub push `[full]` run #461: SUCCESS
- canonical smoke now explicitly includes `tests/test_provider_broker.py`
- runtime restarted: FALSE
- `.env` changed: FALSE

Documentation commits after the green functional/CI checkpoint do not alter runtime behavior. PR #61 must receive its normal GitHub CI result again after documentation changes before merge.

## PROVIDER PRESSURE CONTEXT

Observed provider exhaustion that motivated the maintenance:
- active primary/secondary RPC capacity was exhausted/rate-limited during observation
- failover itself worked but could not succeed when both configured providers were blocked
- strategy quality must not be inferred from WATCH/PAPER_BUY counts collected during provider outage

No provider secret is stored in this document.

Deferred capacity options remain ordinary Phase 8/12 infrastructure choices, not new phases. Additional external providers may fill tertiary/quaternary slots when needed. A dedicated BSC node remains a need-based future option only if quota/cost/latency/load justifies its operational burden.

## COUNTERFACTUAL PRESSURE BOUND

Phase 13 bounded observation contract:
- pending counterfactual Gecko fetch: max 30 pools per scanner refresh
- one bounded multi-pool request for that batch
- remaining pending observations wait for later normal refreshes

This reduces external pressure without changing decision authority or outcome semantics.

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
- successful-wallet tracking → Phase 9
- whale tracking → Phase 9
- news/market intelligence → Phase 5/7 ownership
- Vezir chatbot/operator support → Phase 14
- security hardening → Phase 1/3/10 according to concern

No new phase/era/version tree is permitted for these items.

## MERGE / RUNTIME RULE

Before PR #61 merge:
1. documentation-updated PR smoke/E2E must be green
2. review final PR diff and authority boundaries
3. merge to `main`
4. verify post-merge main SHA/CI
5. fast-forward VPS cleanly
6. do not restart runtime merely for documentation
7. runtime restart/provider env change only with a separate explicit operational need

## CANONICAL DOCUMENTS

- `README.md` — stable project contract
- `ROADMAP.md` — Phase 0–15 ownership map
- `PROJECT_STATE.md` — current continuation checkpoint
- `TEST_RESULTS.md` — historical validation evidence

Historical reports remain evidence, not active architecture.
