# COINOSKOBI CANONICAL PROJECT STATE

Updated: 2026-08-25

## CANONICAL SOURCE

- VPS project: `/root/projects/coinoskobi-dexbot`
- GitHub repo: `anketci54-coder/coinoskobi-dexbot`
- Active canonical branch: `main`
- Canonical backend: `app/api/panel.py`
- Canonical frontend: `app/api/static/index.html`
- Paper DB: `data/paper_trades.db`
- Paper runtime: `coinoskobi-paper-runtime.service`
- Panel runtime: `coinoskobi-panel-api.service`
- Panel port: `8098`

Canonical HEAD before this documentation-only sync:

`cd6348e64c23559334a04c967c805646bf4045ae`

Always verify the current value with:

`git rev-parse HEAD`

and:

`git rev-parse origin/main`

Do not infer current HEAD from chat memory.

## GOVERNANCE

- Phase 0–15: CLOSED.
- Phase 16: NOT OPENED.
- No new Era or V2/V3 replacement architecture.
- No side/test panel architecture.
- Canonical files are modified in place.
- No fake runtime/panel data.
- Missing evidence remains UNKNOWN.
- AI authority = 0.
- Live execution authority = 0.
- Wallet/signing authority = 0.
- Paper runtime only uses paper execution contracts.
- Historical paper DB rows are preserved.
- Hot path must remain fast and bounded.
- Slow/auxiliary providers must not unnecessarily stall the hot path.
- Explicit proven danger may veto.
- UNKNOWN auxiliary evidence is not automatically treated as danger.

## CURRENT PRODUCTION SCOPE

Current development/observation universe:

**BNB Chain (BSC) + PancakeSwap**

The universe size is dynamic.

A value such as 25,406 tokens/pairs is only an observed snapshot and MUST NOT
be hardcoded as the universe size.

Other networks/DEX abstractions may remain in the repository, but current
development effort is focused on BSC + PancakeSwap.

## CURRENT PROVIDER ROLES

- Alchemy: on-chain truth / BNB WSS radar / RPC support
- GeckoTerminal: discovery
- DexScreener: fast indexed market snapshot / market-observation enrichment
- GoPlus: sellability / security / LP evidence
- Honeypot.is: secondary/fallback/dispute evidence

Provider votes are not blindly averaged.

Explicit negative security evidence remains dominant.
Measured on-chain facts remain canonical where directly observable.

## MATHEMATICAL / RISK MAINTENANCE COMPLETED

The post-roadmap maintenance branch
`maintenance/canonical-risk-math`
was fully audited and fast-forwarded into `main`.

Final maintenance integration commit before documentation:

`cd6348e64c23559334a04c967c805646bf4045ae`

Maintenance branch relative to old main at final audit:

- ahead: 39 commits
- behind: 0
- merge base: old canonical main
- final audit: PASS

Completed maintenance includes:

- removal of proven dead/disconnected legacy risk/runner mechanics
- Beta-Binomial flow estimation
- wallet concentration HHI / Shannon measurements
- exact fee-aware constant-product AMM price-impact/capacity math
- empirical exit-capacity reserve floor
- expected MEV-loss plumbing
- evidence-only rug feature vector
- empirical expected shortfall / CVaR
- data-derived fractional Kelly sizing
- pool/source isolated runtime price state
- pool/source isolated EWMA/CUSUM streaming state
- append-only raw market observation history
- history-derived EWMA/CUSUM calibration
- source identity protection
- UNKNOWN preservation
- no invented probabilities
- no invented calibration constants presented as measured truth

## RAW MARKET OBSERVATION HISTORY

`GeckoCache` now preserves append-only market history in the existing cache DB
instead of retaining only the latest snapshot.

Canonical observation identity includes:

- chain
- source
- dex
- pool
- token
- quote token
- observation time

Stored market facts include:

- price
- liquidity
- volume
- buys
- FDV
- market cap
- pool age / creation time where available

Historical evidence is not deleted when the latest scanner cache is pruned.

## STREAMING MATH

Streaming mathematical state is isolated by:

`chain + dex + pair + source + stream-math version`

Cross-source history contamination is prohibited.

Current streaming math includes:

- price log changes
- EWMA variance
- liquidity log changes
- two-sided CUSUM
- history-derived calibration
- WARMING / READY / UNCALIBRATED style evidence states

Calibration remains evidence/math support and does not independently gain
paper, live, wallet or execution authority.

## PAPER POSITION POLICY

New canonical paper positions now default to:

`VUR_KAC`

The engine writes VUR_KAC policy consistently to both:

- opening context
- paper trade row

NORMAL and VUR_KAC lifecycle paths remain separately implemented.

VUR_KAC behavior remains mathematical rather than fixed-profit based:

- fixed profit percentage: false
- fixed holding-time window: false
- dynamic stop behavior
- momentum / flow continuation evidence
- TP1: minimum amount required to neutralize measured initial risk
- TP2: minimum amount required to recover principal
- remaining inventory: runner
- runner exit: persistent deterioration / mathematical VUR_KAC exit
- hard safety exit remains dominant

A large percentage gain alone is NOT an exit command.

The intended asymmetric behavior is:

**keep downside bounded while allowing a healthy winner to continue running.**

## FINAL TEST EVIDENCE

Final VUR_KAC reconciliation:

- targeted regression: 40 passed
- full regression: 1005 passed
- failed: 0
- known warning: 1 upstream `websockets.legacy` deprecation warning
- reconciliation commit:
  `cd6348e64c23559334a04c967c805646bf4045ae`

Final maintenance audit:

- critical regression: 51 passed
- final audit: PASS
- local VUR_KAC state preserved during audit
- old main preserved until deliberate fast-forward

## VPS / GITHUB INTEGRATION

Maintenance was fast-forwarded into canonical `main`.

VPS synchronization result:

- VPS HEAD:
  `cd6348e64c23559334a04c967c805646bf4045ae`
- origin/main:
  `cd6348e64c23559334a04c967c805646bf4045ae`
- worktree: CLEAN
- VUR_KAC canonical source guard: PASS

No force push was used.

## VERIFIED RUNTIME ACCEPTANCE — 2026-08-25

A single controlled paper-runtime restart was performed after integration.

Observed:

- old paper PID: `293487`
- new paper PID: `437659`
- panel PID before: `4118606`
- panel PID after: `4118606`
- panel restart: FALSE
- paper runtime: ACTIVE
- panel runtime: ACTIVE
- paper DB integrity_check: ok
- fatal runtime scan: PASS
- runner started successfully
- scanner job started successfully

Result:

`VPS_GITHUB_RUNTIME_SYNC=PASS`

The panel remained untouched by the paper-runtime deployment.

## NEXT DATA / OBSERVATION WORK

Do NOT open Phase 16.

The next post-roadmap work is an extension of the canonical observation/data
layer for the dynamic BSC + PancakeSwap universe.

Planned observation model:

- COLD: broad universe, cheap periodic observation
- WARM: tokens showing meaningful movement
- HOT: mathematically anomalous / rapidly moving subset with higher-frequency
  observation and native WSS evidence

The universe count is discovered dynamically and changes over time.

Useful market-observation fields to add when backed by real providers include:

- token / pair
- market cap
- price
- age
- transaction count
- volume
- trader count
- 5m change
- 1h change
- 6h change
- 24h change
- liquidity
- gainers / losers classification

The dataset must contain both winners and losers to avoid survivor bias.

Future derived labels may include:

- forward 5m / 15m / 1h / 6h / 24h return
- maximum rise
- maximum drawdown
- time to 2x / 5x / 10x
- liquidity withdrawal / rug evidence
- sellability / realized exit capacity

Raw facts and derived features remain separate.

## PANEL

Panel redesign remains deferred until backend/math/data/runtime work is ready.

There remains one canonical panel only:

**İŞLEM MERKEZİ**

No V2/V3/test panel or additional panel service/port is to be created.

Future panel data must come from real backend/database evidence.

## CURRENT OPEN WORK

1. Documentation sync and handoff closure.
2. Continue natural PAPER runtime observation.
3. Verify the next natural new PAPER OPEN is created with `VUR_KAC`.
4. Verify persisted VUR_KAC mathematical state through its actual lifecycle.
5. Then extend raw observation coverage for the dynamic
   BSC + PancakeSwap universe.
6. Add real txns / traders / multi-window movement / liquidity observations
   only from verified data sources.
7. Use COLD / WARM / HOT prioritization so the whole universe does not incur
   expensive hot-path/provider work.
8. Keep data collection useful for future AI training without granting AI
   decision/trade authority.
9. Do not loosen admission/sizing/safety rules merely because a historical
   token later became a large winner.
10. Do not open Phase 16 / Era / V2 / V3.

## NEW CHAT CONTINUATION

In a new ChatGPT conversation say:

`Coinoskobi reposundaki PROJECT_STATE.md dosyasını baştan sona oku. VPS gerçek durumunu kontrol et. CURRENT OPEN WORK bölümünden sırayla devam et; yeni Phase/Era/V açma.`

Before changing anything verify:

- branch = main
- local HEAD
- origin/main HEAD
- worktree clean/dirty state
- paper service state
- panel service state
- paper DB integrity
- latest runtime cycles

Repository + VPS + runtime DB are the source of truth.
