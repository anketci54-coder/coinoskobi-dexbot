# COINOSKOBI CANONICAL PROJECT STATE

Updated: 2026-08-28

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

Repository, VPS working tree, runtime services and runtime databases together form production truth. Always verify the current SHA directly before apply.

## GOVERNANCE

- The only canonical architecture classification is **PHASE 0-15**.
- Phase 0-15 are CLOSED.
- Phase 15 is the final roadmap phase.
- Do not create Phase 16, ERA, architecture V2/V3, OCR/R-number, post-roadmap, experiment or other parallel roadmap chains.
- PancakeSwap protocol V2/V3 names remain valid where they describe the actual DEX protocol version.
- Maintenance and bug fixes are assigned to the existing Phase 0-15 owner.
- No side/test panel architecture.
- No fake runtime or panel data.
- Missing evidence remains `UNKNOWN`.
- AI trade authority = 0.
- Live execution authority = 0.
- Wallet/signing authority = 0.
- Paper execution remains isolated from live execution.
- Hot-path work remains fast and bounded.
- Heavy/provider work belongs on bounded slow-path/worker paths.

Canonical ownership details live in `ROADMAP.md`.

## CURRENT PRODUCTION SCOPE

Production focus: **BNB Chain (BSC) + PancakeSwap**.

Canonical identity rules:

- token identity is chain-aware
- pool identity is chain + dex + pool
- readable symbols/names are display metadata and never replace identity
- universe size is dynamic and must never be hardcoded

Provider roles:

- RPC/WSS: on-chain truth and native event observation
- GeckoTerminal: discovery and bounded indexed market evidence
- DexScreener: bounded universe market snapshots and readable base/quote metadata
- GoPlus / Honeypot.is: sellability/security evidence

Provider failure or missing evidence is never converted into safe evidence.

## PHASE OWNERSHIP CHECKPOINT

- Phase 0 — early critical fixes and cleanup
- Phase 1 — core infrastructure, SQLite/schema/concurrency/recovery
- Phase 2 — bounded pipeline, queue, UniverseRegistry and discovery
- Phase 3 — risk, sellability, execution cost and entry feasibility
- Phase 4 — deterministic position lifecycle
- Phase 5 — DEX market intelligence and bounded market snapshots
- Phase 6 — exit intelligence
- Phase 7 — flow confirmation, regime and COLD/WARM/HOT seismic state
- Phase 8 — native WSS ingestion, reconnect/reorg/provider resilience
- Phase 9 — wallet/entity/smart-money intelligence
- Phase 10 — adversary/scam/MEV intelligence
- Phase 11 — learning/calibration/outcome memory; proposal-only
- Phase 12 — operational paper runtime, restart/recovery and cross-phase E2E
- Phase 13 — paper/counterfactual outcome calibration and data integrity
- Phase 14 — canonical Command Center, panel and readable display metadata
- Phase 15 — final operational validation and explicit-approval micro-live boundary

## 2026-08-28 CANONICAL CLEANUP AND TOKEN-NAME CLOSURE

PR #27 was merged into `main` after canonical smoke/E2E and full repository regression passed.

Accepted implementation/runtime code SHA:

`c0dfb5aab8af75cb5b0944a670e9982585c5ad70`

The merge:

- repaired readable universe token/pair display names using real bounded DexScreener metadata
- kept pool/token identity unchanged
- kept panel read-only and authority-free
- folded legacy parallel architecture/workstream labels into Phase 0-15 ownership
- removed the standalone full-universe architecture document
- removed the standalone panel UI policy document
- removed standalone WARM research scripts and their script-only tests
- renamed retained OCR/runtime-repair regression coverage under Phase 12 ownership

No replacement disposable script or parallel roadmap was added.

## VPS RUNTIME ACCEPTANCE

The production VPS was fast-forwarded cleanly to accepted implementation SHA `c0dfb5aab8af75cb5b0944a670e9982585c5ad70`.

Acceptance evidence:

- branch: `main`
- worktree: clean
- paper runtime: active
- panel runtime: active
- universe shadow: enabled
- PancakeSwap V2/V3 start blocks: configured
- WSS: configured
- display metadata table: created by canonical universe observation path
- display metadata rows at acceptance: 32
- named metadata rows at acceptance: 32
- visible panel universe rows: 40
- readable display-name matches: 36
- readable display-name coverage: 90.00%
- display source: `UNIVERSE_POOL_DISPLAY_METADATA_V1`
- frontend display contract: PASS
- `data/cache/cache.db`: integrity/quick check `ok`
- `data/paper_trades.db`: integrity/quick check `ok`

The remaining unnamed visible rows are not filled with fabricated names; they remain fallback/unknown until real provider metadata is observed.

## REPOSITORY CLEANUP SEAL

After runtime acceptance, obsolete remote branches were audited against `main` and removed. The final remote-branch audit reported:

- non-main remote branches: 0
- canonical remote branch: `main` only
- production worktree: clean
- paper runtime: active
- panel runtime: active

Closed/merged historical pull requests and historical phase-scoped validation reports remain audit history, not active architecture branches or roadmap chains.

## CURRENT STATUS

- No active integration candidate.
- No open pull request is required for the accepted runtime state.
- Canonical architecture is Phase 0-15 only.
- Runtime acceptance for the token-name repair is PASS.
- Repository branch cleanup is PASS.
- Production services are active.
- Display-name repair is live with real provider-backed metadata.

This documentation seal is non-runtime. If its commit advances `main` beyond the accepted implementation SHA, the VPS needs only a clean `git pull --ff-only` synchronization; no service restart is required for this documentation-only change.

## NEXT MAINTENANCE RULE

For any future work:

1. assign it to the existing Phase 0-15 owner
2. make a targeted change
3. run targeted tests
4. run canonical smoke/E2E
5. run full regression when the scope warrants it
6. merge to `main`
7. fast-forward the VPS only after GitHub is green
8. verify runtime/DB evidence before sealing

Do not reopen a parallel roadmap or create disposable persistent scripts.