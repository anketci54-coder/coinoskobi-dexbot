# COINOSKOBI CANONICAL PROJECT STATE

Updated: 2026-09-17

## CANONICAL SOURCE

- Repository: `anketci54-coder/coinoskobi-dexbot`
- Production branch: `main`
- Verified runtime/code baseline SHA: `3eaabe8c73c6b22bd0e0dd793afad02b07da5425`
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
- Within that owner, reuse/update the matching existing flat-letter subphase first; only work that does not fit any existing subphase and needs distinct durable ownership may take the next unused flat letter under the same Phase.
- Nested subphase numbering, duplicate architecture and parallel runtime/provider/router paths are forbidden.
- Unused/duplicate/superseded executable scripts, modules, configs and test helpers are removed after reference audit and tests; historical audit/evidence documents may remain as evidence.
- Canonical maintenance classification is governed by `README.md` and `ROADMAP.md`; new sessions/agents must read them before planning or applying work.
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

## 2026-09-17 PAPER PRICE EVIDENCE MAINTENANCE SEAL

Status: **VALIDATED / MERGED / DEPLOYED / RUNTIME-SMOKE PASS**.

Ownership:
- position lifecycle / hot open-position handling → Phase 4
- operational paper runtime / provider operability → Phase 12
- no new phase/ERA/version tree opened

Final verified production checkpoint:
- PR #187 merged into `main`
- merge commit / deployed runtime SHA: `3eaabe8c73c6b22bd0e0dd793afad02b07da5425`
- VPS `main` synchronized to `origin/main`
- VPS worktree clean at post-deploy verification
- `coinoskobi-paper-runtime.service`: active
- post-restart PID observed: `3067324`
- runtime started both `paper_manager` and `paper_hot_manager`

Validated maintenance contracts:
- fresh sellability local evidence is preferred over stale risk/risk-gate local evidence for paper sizing
- VUR_KAC requires established positive continuation; one-bar rebound after a negative prior return is not READY
- deteriorating/unavailable liquidity cannot promote a VUR_KAC entry
- `gecko_pool_cache.updated_at` remains the market-quality/scanner timestamp
- independent `price_updated_at` records provider/WSS price freshness
- stale exact open-position prices fail closed instead of falling through to token-cache fallback pricing
- stale cache values cannot anchor the WSS open-position price bridge
- WSS/provider price refreshes update price freshness without refreshing market-quality freshness
- no stop/fill is fabricated when current price evidence is stale

Final validation evidence:
- targeted maintenance suite: **27 passed / 0 failed**
- full repository regression: **1635 passed / 0 failed**
- full regression runtime: **441.18 s**
- warning count: **1**
- recurring warning: dependency-owned `websockets.legacy` deprecation
- `git diff --check`: PASS
- post-deploy runtime critical-error scan: empty for traceback, SQLite thread error, database locked, exception, fatal and critical patterns
- production cache schema confirmed both `updated_at` and `price_updated_at`
- post-deploy service remained active while scanner, fast-watch and pipeline cycles continued

One earlier full regression exposed the canonical timestamp invariant before the final correction:
- **1633 passed / 1 failed**
- failing test: `test_price_only_refresh_preserves_market_quality_timestamp`
- correction: market-quality freshness and price freshness were separated instead of advancing the shared timestamp on price-only refresh

GitHub Actions note:
- PR smoke jobs failed before producing any workflow steps; this was treated as a separate CI/runner infrastructure condition, not as a passing code-validation signal
- repository acceptance therefore relies on the recorded VPS targeted/full regression and post-deploy smoke for this maintenance seal

Observed non-blocking provider warnings after deploy:
- `DexScreener snapshot fallback unavailable: 'NoneType' object is not iterable`
- Universe discovery `HTTPError` / `ConnectionError`
- runtime remained active; these warnings did not alter the price-evidence maintenance acceptance

Natural `NORMAL` PAPER TP1 → TP2 → TP3/runner → close remains a separate Phase 4/12 natural-runtime E2E observation target and must not be manufactured by weakening admission, sizing, LP protection, sellability, risk or hard-block gates.

## 2026-09-16 FINAL MAINTENANCE SEAL

Status: **VALIDATED WITH NATURAL NORMAL PAPER RUNTIME E2E STILL PENDING**.

Final verified production checkpoint:
- runtime/code baseline SHA: `a75dd8d7bb4494da4934334a5829e4f3385e9e90`
- VPS worktree: clean at verification
- local `main` vs `origin/main`: synchronized at verification
- paper runtime service: active
- `paper_trades.db` integrity: `ok`
- open paper positions at earlier final smoke: `0`
- last paper trade id at earlier final smoke: `39`

Repository-wide regression evidence before the Phase 13D forensic-learning closure:
- final branch HEAD: `fc0dead79ae7385337d95644a6336cf26be3dcfc`
- targeted final suite: **33 passed / 0 failed**
- full repository suite: **1630 passed / 0 failed**
- full runtime: **414.31 s**
- recurring dependency warning: `websockets.legacy` deprecation only

Phase 13D forensic-learning closure:
- PR #186 merged into `main`
- merge commit: `a75dd8d7bb4494da4934334a5829e4f3385e9e90`
- bounded paper-loss forensics and missed-opportunity blocker attribution are active
- legacy PnL is preserved with currency-aware lifecycle evidence; BNB values are not relabeled as USDT
- durable counterfactual history is fail-open for optional forensic reads
- malformed forensic payloads are normalized without aborting the unified readmodel
- RAM/durable duplicate decisions are deduplicated by shared observation identity
- post-promotion price moves are excluded from missed-opportunity bucketing and example maxima
- authority remains proposal/read-only; trade/wallet/signing/live/execution authority remains false
- no automatic threshold/config/source-code application was introduced

Post-merge runtime smoke on merge SHA:
- VPS deployed SHA: `a75dd8d7bb4494da4934334a5829e4f3385e9e90`
- `coinoskobi-paper-runtime.service`: **active (running)**
- wallet outcome hydration: `READY`
- `paper_trades.db` integrity: **ok**
- restart/shutdown lifecycle: **clean**
- observed non-blocking warning: `DexScreener snapshot fallback unavailable: 'NoneType' object is not iterable`
- runtime remained active after that warning
- `POST_MERGE_RUNTIME_SMOKE=PASS`

Final external review evidence for the Phase 13D closure included Codex, Strix, CodeRabbit and Copilot review cycles. Reported P1/P2 forensic correctness, lifecycle, currency, malformed-payload, runtime-availability and promotion-attribution findings were addressed before merge; resolved review threads were closed before final merge.

Final timestamp-integrity maintenance retained from the preceding seal:
- PR #182 merged onto the runtime/code baseline
- strict canonical aware timestamp grammar enforced in both runtime-learning outcome integrity and paper risk calibration
- malformed/naive/invalid outcome fingerprints fail closed
- invalid stored outcome fingerprints cannot bootstrap paper sizing

Real PAPER runtime lifecycle evidence retained:
- trade id `39`
- mode: `AUTO`
- trade type: `VUR_KAC`
- status: `CLOSED`
- close reason: `MATHEMATICAL_NO_UPSIDE_EXIT`
- partial realization count: `0`
- remaining token amount: `0`
- remaining cost basis: `0`
- PnL identity: PASS
- net PnL match: PASS
- full-exit invariant: PASS

The VUR_KAC real runtime lifecycle and accounting path are therefore runtime-proven. A natural `NORMAL` PAPER trade has still not occurred in the durable runtime database; TP1 → TP2 → TP3/runner → close remains pending as a natural runtime E2E observation. This evidence must not be manufactured by weakening admission, sizing, LP protection, sellability, risk, or hard-block gates.

Documentation-only seal commits may move repository `main` beyond the runtime/code baseline SHA without changing runtime behavior; verify the current repository HEAD directly before future work.

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
- natural NORMAL PAPER lifecycle runtime E2E observation → Phase 4/12
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

## 2026-09-17 NEUTRAL QUOTE FLOW SEMANTICS SEAL

Status: CLOSED_VERIFIED_GITHUB_MERGED_DEPLOYED

Merge / deployed commit:
- 3b5bdd62b04b6b854dc04410457d86c7575905c7

PR:
- #188 Fix neutral quote flow semantics

Behavior:
- measured quote flow > 0 => SUPPORTING
- measured quote flow < 0 => OPPOSING
- measured quote flow == 0 => NEUTRAL
- missing quote flow => UNKNOWN
- QUOTE_FLOW_NOT_SUPPORTING_MOVE applies only to measured negative flow
- recovery breakout still requires strictly positive quote flow
- no risk, sizing, sellability, hard-block, or paper admission gate was weakened

Validation:
- targeted regression: 48 passed, 1 warning
- full regression: 1637 passed, 1 warning
- git diff --check: clean
- service restart: PASS
- runtime critical-error smoke: PASS
- post-deploy runtime evidence: 20 zero-flow samples
- zero-flow classified NEUTRAL: 20/20
- zero-flow classified OPPOSING: 0/20

GitHub Actions:
- workflow infrastructure/startup failure persisted
- smoke job had no executable steps / no runner execution evidence
- full job was skipped
- CI is therefore not recorded as green

Natural NORMAL PAPER TP lifecycle remains an observation item and was not forced.
## RESERVE_COLLAPSE_MAINTENANCE_SEAL_20260917

Status: CLOSED_VERIFIED_DEPLOYED

Scope:
- Real-world candidate 60615 / exact Pancake V2 WBNB-JOE pool forensic.
- Confirmed historical quote-reserve collapse from approximately 17.10235997081519 WBNB to 0.01576356812299259 WBNB, followed by near-zero residual liquidity.
- Added evidence-only reserve-collapse classification.
- Exit feasibility now exposes reserve-collapse state, withdrawal fraction and catastrophic-collapse evidence.
- Unified opportunity classification vetoes HOT and returns WATCH / CATASTROPHIC_RESERVE_COLLAPSE when catastrophic depletion is confirmed.
- No trade, wallet, signing, live, paper or execution authority was introduced.
- Existing Risk Gate / sellability / sizing safety boundaries were not weakened.

GitHub:
- Feature commit: 371c82fc58d5a46b2d526e83f9363f3f1df2d773
- PR: #189
- Merge commit: 49aa2916bb08b91f5bda21b09d2c64228f834110
- Security review: Strix reported no security issues.
- GitHub Actions PR-head run 35196980907 was not green: smoke failed before useful job steps and full was skipped; this was not treated as pytest-pass evidence.

Deployment:
- main synced to merge commit.
- coinoskobi-paper-runtime.service restarted successfully.
- exact-pool post-deploy smoke PASS.
- historical catastrophic-collapse classifier PASS.
- UnifiedScore catastrophic-collapse WATCH veto PASS.
- post-deploy runtime traceback / SQLite thread / database-locked audit PASS.

Separate existing observation remains:
- Natural NORMAL PAPER TP1 -> TP2 -> TP3/runner -> close E2E remains pending a natural qualifying trade.
- No trade is to be forced and no gate is to be weakened for that observation.
## PAPER_10K_RESET_SEAL_20260917

Status: CLOSED_VERIFIED_DEPLOYED

Active run:
- run_key: PAPER_10K_20260917T081936Z
- starting capital: 10000.0 USDT
- historical trade boundary: id <= 39
- new run first trade id: 40
- historical trades preserved in same DB
- historical realizations preserved in same DB
- candidate history preserved in same DB
- no historical rows deleted

Accounting:
- runtime available capital is scoped to the single ACTIVE paper run
- panel active-period performance uses the same run boundary
- panel starting capital uses the active run value
- historical paper rows remain available for all-time analysis

GitHub:
- accounting PR #190 merged as b3d30d5119efd4f69746c0ec3d3685fa878829a3
- panel PR #191 merged as 7fdd2899b0dbf8f8d09f8cad9e01c8329aba6532
- GitHub CI was not recorded as green because smoke failed before useful steps and full was skipped

Runtime:
- paper runtime active after deploy
- panel service active after deploy
- final 10K reset audit PASS
