# COINOSKOBI CANONICAL PROJECT STATE

Updated: 2026-08-23

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

The active canonical HEAD must always be read from:

`git rev-parse HEAD`

and must match:

`git rev-parse origin/main`

Do not infer HEAD from chat memory.

## GOVERNANCE

- No Phase 16.
- No new Era.
- No V2/V3 replacement architecture.
- No side/test panel architecture.
- No patch/bak/old/diff junk.
- Modify canonical files in place.
- No fake panel/runtime data.
- Missing evidence remains UNKNOWN.
- AI authority = 0.
- Live execution authority = 0.
- Wallet/signing authority = 0.
- Paper runtime may trade only through existing paper contracts.
- Do not delete historical paper DB rows for cosmetic reasons.

## LAST SEALED FUNCTIONAL BASE

Mathematical Vur-Kac base seal:

`45902f16b6e5b4cc58f79ed2d6f59d4283078560`

At that seal:

- fixed profit percentage = false
- fixed Vur-Kac time window = false
- post-entry price momentum = bound
- native flow momentum = bound
- native flow acceleration = bound
- continuation edge = bound
- TP1 = minimum measured-risk neutralization
- TP2 = minimum principal recovery
- runner = persistent exhaustion exit

## LAST VERIFIED RUNTIME OBSERVATION BEFORE DIAGNOSTIC FIX

Paper runtime was active and fault-free.

Observed after Vur-Kac activation:

- runtime cycles observed: 13
- open paper positions: 0
- closed PAPER_10K_V2 positions: 26 total
- active panel period: ID 16+
- active-period trades: 11
- active-period wins: 4
- active-period losses: 7
- active-period realized net PnL: approximately -863.8687580557469 USDT
- global Vur-Kac runtime state observed: 0
- Vur-Kac exit observed: 0

This does NOT mean Vur-Kac failed.
There was no open position available to exercise it.

## CURRENT DIAGNOSTIC CORRECTION

The prior runtime collapsed two different failures into:

`MATHEMATICAL_PLAN_BLOCKED`

Canonical runtime now separates:

- `PLAN_BLOCKED`
- `POSITION_SIZING_BLOCKED`
- defensive `SELLABILITY_NOT_OK`

For WATCH decisions it exposes separately:

- plan blockers
- plan unknowns
- sizing blockers
- sizing reason
- resulting entry amount
- safe quote reserve
- empirical risk distance
- empirical gap multiplier
- empirical cost uncertainty
- effective edge

Admission mathematics is NOT relaxed by this diagnostic correction.

## COUNTERFACTUAL SEMANTICS

`MISSED_OPPORTUNITY` is a counterfactual price-direction label.

It means only that the later observed mark price was higher under the
counterfactual classification contract.

It does NOT prove:

- net trade profit
- executable profit
- sellability at evaluation time
- profit after gas/tax/slippage/route friction
- realizable Vur-Kac profit

Never use the count alone to loosen admission.

## CURRENT LOCAL WSS LIFECYCLE CORRECTION

Root cause found from real runtime observation:

- scanner/runtime continued for 134 cycles
- candidate analysis continued
- runtime process had no established TCP connection at audit time
- repeated candidates successfully accumulated price history
- repeated candidates successfully accumulated LP persistence
- market-quality evidence remained not ready
- participation evidence remained unknown

The canonical local correction therefore changes only WSS lifecycle:

1. An idle websocket receive window is no longer treated as a transport failure.
2. Websocket ping/pong remains responsible for connection liveness.
3. A previously-started WSS service whose worker thread has died is restarted by the normal pair refresh path.
4. An unchanged pair list also self-heals a dead previously-started service.
5. Admission thresholds, mathematical trade planning, sizing, Vur-Kac, wallet authority and live authority are unchanged.

This correction is not considered sealed until:

- targeted tests pass
- full test suite passes
- paper runtime is restarted once
- panel PID remains unchanged
- persistent WSS/TCP connectivity is observed
- runtime fatal scan passes

WSS lifecycle and broad native observation scope were validated together against the real Alchemy BNB WebSocket runtime.

## NATIVE WSS OBSERVATION SCOPE

Canonical behavior:

- Alchemy BNB is the active WSS provider.
- Native WSS observation is independent from ingress admission.
- Current verified Pancake V2 scanner pools are observed before they
  become decision-eligible.
- Pair membership verification remains mandatory.
- WSS target count remains bounded to 256.
- Admission, mathematical planning, position sizing, Vur-Kac and all
  authority locks remain unchanged.
- Missing market evidence remains UNKNOWN and cannot authorize entry.

## CURRENT OPEN WORK

One cause -> one correction -> one closure.

Latest sealed canonical HEAD:

`e86a40d895a6d1cc16d5a8b94df9bee6cc525e21`

Final acceptance at this seal:

- full regression: 1061 PASS / 0 FAIL
- empirical calibration: READY
- calibration reason: EMPIRICAL_OUTCOME_CALIBRATION
- bootstrap blockers: cleared
- observed PLAN_BLOCKED: 3
- observed POSITION_SIZING_BLOCKED: 0
- GAP_RISK_UNOBSERVED: 0
- COST_UNCERTAINTY_UNOBSERVED: 0
- active paper trades at acceptance: 0
- DB quick_check: ok
- paper runtime: active
- panel runtime: active
- service restart during final acceptance: false

The blocker-distribution question is therefore resolved for the observed
acceptance window: empirical position sizing was not the remaining blocker.
Admission mathematics must not be loosened from this evidence alone.

Current task:

1. Keep the canonical paper runtime operating naturally.
2. Observe the next natural new paper OPEN.
3. Verify real `vur_kac_*` state creation for that position.
4. Verify persisted mathematical state from entry through close.
5. If profitable momentum weakens, verify:
   - TP1 minimum risk neutralization
   - TP2 minimum principal recovery
   - runner behavior / mathematical Vur-Kac exit
6. Do not loosen admission, sizing or safety gates without new runtime evidence.

## NEW CHAT CONTINUATION

In a new ChatGPT conversation, say:

`Coinoskobi reposundaki PROJECT_STATE.md dosyasını oku, VPS gerçek durumunu kontrol et ve CURRENT OPEN WORK bölümünden devam et.`

Before changing anything, verify:

- current branch
- local HEAD
- origin branch HEAD
- clean/dirty worktree
- paper service state
- panel service state
- DB quick_check
- latest runtime cycles

The VPS/runtime/DB are the source of truth for current operational state.
