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

Repository, VPS working tree, runtime services and runtime databases together form production truth. Never infer a current production SHA from historical chat text; verify it directly before apply.

## GOVERNANCE

- The only canonical architecture classification is **PHASE 0–15**.
- Phase 0–15 are CLOSED.
- Phase 15 is the final roadmap phase.
- Phase 16 is not opened.
- Do not create ERA, V2/V3, OCR/R-number, post-roadmap, experiment or other parallel roadmap chains.
- Maintenance and bug fixes are assigned to the existing Phase 0–15 owner.
- No side/test panel architecture.
- No fake runtime or panel data.
- Missing evidence remains `UNKNOWN`.
- AI trade authority = 0.
- Live execution authority = 0.
- Wallet/signing authority = 0.
- Paper execution remains isolated from live execution.
- Historical paper/database evidence is preserved unless an explicit migration requires otherwise.
- Hot-path work remains fast and bounded.
- Heavy/provider work belongs on bounded slow-path/worker paths.

Canonical ownership details live in `ROADMAP.md`.

## CURRENT PRODUCTION SCOPE

Current observation/development focus:

**BNB Chain (BSC) + PancakeSwap**

Universe size is dynamic and must never be hardcoded.

Canonical identity rules:

- token identity is chain-aware
- pool identity is chain + dex + pool
- readable symbols/names are display metadata and never replace identity

## PROVIDER ROLES

- RPC/WSS provider: on-chain truth and native event observation
- GeckoTerminal: discovery and bounded indexed market evidence
- DexScreener: bounded universe market snapshots and readable base/quote metadata
- GoPlus / Honeypot.is: sellability/security evidence

Provider votes are not blindly averaged. Explicit proven danger may veto. Provider failure or missing evidence is not converted into safe evidence.

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

## CURRENT INTEGRATION CANDIDATE

PR #27: `fix/phase14-token-names-and-readable-density`

Purpose:

1. Repair readable universe token/pair display names using real bounded provider metadata.
2. Keep pool/token identity unchanged.
3. Keep panel read-only and authority-free.
4. Fold legacy parallel architecture/workstream labels into Phase 0–15.
5. Remove obsolete standalone experiment/policy/architecture files where their canonical rules already exist in `ROADMAP.md`.
6. Preserve useful regression coverage under Phase-scoped test names.

Production evidence that motivated the display-name repair:

- visible universe rows checked: 40
- `gecko_pool_cache` readable-name matches: 0
- Gecko cache therefore cannot be the canonical full-universe display-name source

The existing bounded DexScreener universe snapshot path already receives `baseToken` / `quoteToken` symbol/name facts. Those facts belong to Phase 5 market metadata and are projected read-only by Phase 14.

## CLEANUP STATE

The integration candidate removes active parallel-roadmap artifacts including:

- standalone full-universe architecture document
- standalone panel UI policy document
- standalone WARM research scripts and their script-only tests
- obsolete OCR/runtime-repair test filenames

Useful OCR/runtime-repair regression behavior is retained under Phase 12 test ownership rather than discarded.

Historical phase-scoped validation reports may remain as audit evidence. They are not active roadmap chains.

## VALIDATION GATE

Required order before production synchronization:

1. candidate branch targeted tests
2. canonical smoke/E2E
3. full repository regression
4. PR mergeability check
5. merge into `main`
6. verify final `origin/main` SHA
7. VPS preflight: branch/main, HEAD, origin/main, clean worktree, service states, DB health
8. fast-forward VPS to exact final main SHA
9. apply only required migration/runtime change
10. verify paper runtime, panel runtime, DB integrity and real panel data
11. seal VPS HEAD = origin/main and clean worktree

No production apply is allowed before the GitHub validation gate is green.

## CURRENT STATUS

- PR #27 is the active integration candidate.
- Cleanup/phase-ownership rewrite is included in that candidate.
- Canonical smoke/E2E has passed on the cleanup line before the final documentation sync.
- A full repository regression is required on the final candidate head.
- VPS has not yet been synchronized to PR #27.
- Do not restart or alter production services merely to test an unmerged candidate.

## NEXT ACTION AFTER GREEN CI

When the final candidate head is fully green:

- merge PR #27 into `main`
- record the exact final main SHA
- run one controlled VPS preflight/synchronization block
- verify real display-name coverage and runtime health
- update this checkpoint only if production facts changed
