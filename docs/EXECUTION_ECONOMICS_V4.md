# Execution Economics V4 — canonical design

Status: DESIGN SEALED FOR IMPLEMENTATION
Scope: PAPER first; no live/wallet/signing authority.

## Decisions that must survive chat/session changes

### Exit lifecycle
- NORMAL becomes TP1 + runner.
- Current TP2 is not part of the target lifecycle.
- TP1 exists to neutralize measured initial risk / recover required capital.
- Remaining inventory becomes a real runner.
- Runner profit protection must use executable net economics, not mark-price ROI.
- High-water mark target is executable net PnL, not raw highest price.
- Post-entry volatility/history controls the trailing distance.
- Never fabricate a stop fill between observations; use observed/executable evidence.

### Canonical execution economics
Baseline executable output must come from the controlled pinned-block/fork route simulation whenever available.
That baseline already captures route fee, size-dependent AMM price impact and token transfer behavior that occurred in the simulation.
Do not subtract those components a second time.

Gas:
- use executed/simulated gasUsed * effective gas price when execution evidence exists;
- estimateGas/current gas price is pre-execution evidence only;
- never silently convert missing gas to zero.

FOT/tax:
- metadata is advisory;
- actual fork balance deltas are stronger evidence;
- standard SELL REVERT followed by same-block/same-amount FOT SUCCESS is authoritative route evidence.

Slippage:
- observed/expected execution slippage and allowed slippage tolerance are distinct fields;
- slippage_pct must not be assumed to be the transaction minOut tolerance;
- MEV bounding requires an explicit slippage_tolerance_pct / minOut contract.

MEV/sandwich:
- do not require an invented point estimate;
- classify economic evidence as BOUNDED or UNBOUNDED;
- with baseline executable output Q and explicit allowed slippage s, victim adverse-output loss is bounded by the minOut headroom:
  mev_loss_upper_bound_usd = Q * s (s expressed as a fraction);
- this is a conservative decision reserve, not a claim that the attack will occur;
- price impact/AMM fee/FOT already in Q must not be deducted again;
- private/protected routing lowers exposure classification but does not make reserve zero unless measured calibration supports a lower reserve;
- if tolerance/minOut or executable output basis is unavailable, state is UNBOUNDED and admission remains fail-closed;
- expected MEV loss may be reported separately only when attack probability and conditional loss are calibrated/measured.

### Admission rule
For a tentative position size, compute:
conservative_net_edge = executable_edge - gas - mev_adverse_selection_reserve - stale_quote_reserve
where executable_edge is based on simulated executable output and contains no duplicate AMM/FOT deductions.

Accept only if the conservative net edge remains above the required safety margin.
If it does not, reduce size and recompute; if no positive safe size exists, reject.

### Evidence hierarchy
1. Pinned fork / actual transaction balance delta and receipt
2. Current RPC quote / estimateGas with explicit block provenance
3. Measured pool reserves and deterministic AMM math
4. Calibrated empirical distributions
5. Provider metadata
6. Unknown — never fabricated

## Recent incident anchors
- 522/523/524 exposed standard-vs-FOT SELL route failure.
- 523 gave back a large marked profit because SELL execution was reverting.
- 525 demonstrated observation-gap risk: a protection threshold is not a guaranteed fill.
- 522 demonstrated that positive mark-price ROI can still be negative executable net PnL after transfer behavior.
- Recent TP2 contribution was small while it materially reduced runner inventory; target lifecycle is TP1 + runner.

## Non-goals
- no historical PnL rewrite;
- no invented MEV probability;
- no arbitrary fixed MEV percentage;
- no double-counting route fee, price impact, FOT or slippage;
- no relaxation of hard sellability/risk gates.
