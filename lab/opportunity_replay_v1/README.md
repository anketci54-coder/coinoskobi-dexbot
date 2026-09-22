# Opportunity Replay Lab v1

Purpose: a **read-only, causal replay laboratory** for Coinoskobi historical WARM/HOT market-state events.

This is deliberately **not a new Phase** and does not change production runtime, PAPER admission, RiskGate, live authority, wallet/signing/order-create authority, or existing trading thresholds.

## Scope

The lab replays historical market observations from `data/cache/cache.db` in chronological order.

Every event is keyed by `chain + dex + pool`; different pools for the same token are never merged.

The first dataset covers both:

- `WARM` transitions
- `HOT` transitions
- WARM -> HOT promotion before the decision point
- state at the decision point

The lab must eventually choose exactly one action:

- `ALMA`
- `VUR_KAC`
- `NORMAL`

NORMAL keeps the existing semantic lifecycle:

`ENTRY -> TP1 -> TP2 -> TP3 trend runner -> final exit`

VUR_KAC remains full-exit-only.

## Core anti-lookahead rule

At replay time `t`, the decision engine may use only observations with `observed_at <= t`.

Future observations are permitted only in the **evaluation** section of a row, never in decision features.

Chronological train/test separation is mandatory before any parameter is accepted.

## Capital / sizing contract

Initial replay capital:

`capital_usdt = 10000`

Every simulated trade must explicitly record:

- `decision`
- `entry_state` (WARM or HOT)
- `entry_price`
- `entry_amount_usdt`
- `entry_amount_pct_of_capital`
- `risk_amount_usdt`
- `stop_loss_price`
- `stop_distance_pct`
- estimated friction / costs
- realized exit path
- net P&L
- drawdown

Position size is not a fixed 3-5 USD amount. It must ultimately be derived from:

`trade type + entry quality + invalidation/SL distance + exit liquidity + expected edge + capital risk budget`

Large nominal VUR_KAC positions are allowed only when the evidence supports a tight invalidation point and bounded dollar risk.

## v1 work order

1. Build a causal WARM/HOT event dataset.
2. Quantify WARM vs HOT behavior and WARM -> HOT promotion value.
3. Derive candidate features without using future data.
4. Define/fit ALMA vs VUR_KAC vs NORMAL on chronological training data.
5. Freeze parameters.
6. Blind-test on later unseen history.
7. Compare against the current PAPER decision/exit behavior.
8. Only if the blind test materially improves net P&L / drawdown / risk-adjusted return, consider PAPER runtime integration.

## v1 dataset fields

The first extractor records:

- event time/state
- decision time/state
- WARM -> HOT promotion before decision
- event price
- decision price
- pre-decision return
- pre-decision maximum favorable/adverse movement
- pre-decision sample count
- latest liquidity, 5m volume, buys, sells, txns and 5m change known at decision time
- future MFE/MAE and returns at fixed horizons for evaluation only
- time to 24h peak
- time until price first falls below the decision price

## Safety

The extractor opens SQLite with `mode=ro`.

No database write is allowed.
No provider/network call is allowed.
No production service is restarted.
No production module is imported for authority or execution.
