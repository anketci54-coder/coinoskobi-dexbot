# Astra High — NORMAL PAPER Profit Protection Root-Cause Audit

Repo: `/root/projects/coinoskobi-dexbot`  
Branch: `fix/paper-risk-profit-core`  
Target HEAD before this audit file: `904149d8c0bbd585697e3b8158fb89ea1b8cf40c`

## Rules
- READ-ONLY audit of runtime behavior and code paths.
- Do not modify application code.
- Do not create a PR.
- Do not change tests or fixtures.
- Do not refactor.
- Do not propose a fix until the runtime root cause is proven.
- Passing tests are NOT proof of correct runtime behavior.

## Primary problem

NORMAL PAPER positions can reach large unrealized profit, but profit protection does not engage and most of the peak profit is given back.

Observed examples:

Trade #277:
- peak PnL ≈ +$6,366
- realized PnL ≈ +$1,837
- giveback ≈ $4,529

Trade #284:
- peak PnL ≈ +$3,582
- later PnL ≈ +$334
- position remained OPEN
- `tp1_done=0`
- `tp2_done=0`
- `runner_active=0`
- TP1 mathematics/state was `null`

## Core question

**Why can a NORMAL PAPER position become highly profitable while TP/profit-lock/runner never activates, allowing thousands of dollars of peak PnL to be given back toward stop-loss?**

## Trace the actual runtime path

Follow the real execution path:

`open NORMAL position`
→ `price observation`
→ `unrealized PnL / return computation`
→ `high / peak mutation`
→ `TP threshold calculation`
→ `TP1 eligibility`
→ `TP1 state mutation`
→ `TP2 eligibility`
→ `runner activation`
→ `profit-lock / trailing logic`
→ `exit decision`
→ `exit price`
→ `realized PnL`

Do not infer architecture from names alone. Prove runtime callers and reachable paths.

## Investigate specifically

1. Where NORMAL TP1/TP2 thresholds are computed.
2. Under which conditions TP mathematics can remain `null`.
3. Whether TP thresholds are created at entry, after entry, lazily, or only for some strategy/mode.
4. Whether NORMAL positions can exist without initialized profit-protection state.
5. Exact predicates required for `tp1_done`, `tp2_done`, and `runner_active`.
6. Whether those predicates depend on fields that are missing, stale, null, or never persisted.
7. Whether peak/high is updated correctly but TP evaluation uses another price/PnL field.
8. Whether ordering causes peak mutation first but TP evaluation skipped or evaluated against stale state.
9. Whether NORMAL and VUR_KAC use different protection paths and NORMAL lacks required initialization.
10. Any legacy/fallback/direct PAPER path that creates NORMAL positions without TP/profit-lock configuration.
11. Any exception/fail-open branch that silently skips protection logic.
12. Whether restart/persistence can lose TP/runner state.
13. Whether DB schema defaults (`NULL`, `0`, missing JSON fields) disable TP logic.
14. Whether close logic can fall through to `NORMAL_STOP_LOSS` even after large positive peak profit.
15. Whether TP/profit-lock functionality exists in code/tests but is not runtime-reachable for the affected NORMAL positions.

## Trades #277 and #284

If database/runtime history is available, reconstruct as much as possible:

- entry state
- entry price
- amount/quantity
- TP parameters at creation
- peak/high evolution
- TP state transitions
- runner state transitions
- final/last price
- exit reason
- realized PnL

Do not fabricate missing historical state.

## Evidence format

For every finding use one of:

### VERIFIED FACT
- exact `file:function/path`
- actual runtime caller/path
- evidence
- why it causes or cannot cause the observed giveback

### INFERENCE
- evidence
- missing proof

### UNKNOWN
- exact minimum runtime/data measurement required

## Final output only

A) Verified root cause(s)

B) Strong but unproven suspects

C) Previous assumptions proven false

D) Exact causal chain explaining how a NORMAL position can reach large peak profit without TP/profit-lock/runner engagement

E) Minimum correction surface — identify files/functions/state only; DO NOT implement

F) Runtime acceptance criteria for a future fix

Acceptance criteria must include evidence that a real NORMAL PAPER trade can:

`entry`
→ reach TP1 threshold
→ persist `tp1_done`
→ activate the intended protection/runner path
→ preserve state across subsequent observations/restart where applicable
→ exit according to the intended protection logic

and that peak-profit giveback is no longer caused by missing/uninitialized TP state.

Do not conclude “fixed” from unit tests.

## Most important question

**For affected NORMAL PAPER positions, what exact runtime condition keeps TP1/TP2/profit-lock/runner inactive even after the position has already generated substantial profit?**
