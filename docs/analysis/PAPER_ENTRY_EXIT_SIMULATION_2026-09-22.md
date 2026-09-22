# PAPER Entry/Exit Offline Simulation — 2026-09-22

## Scope
Offline historical replay only.

- Runtime unchanged
- Panel unchanged
- Database read-only
- No live authority

## Candidate Rule
- Entry: `price_acceleration <= -0.05`
- Estimated round-trip cost: `<= 2%`
- TP: `+10%`
- SL: `-7%`

## Final Result
- Selected: 49
- Evaluable: 48
- Data-quality excluded: ID 43
- Average net return: +1.91%
- Win rate: 58.3%
- Sum net returns: +91.75%
- TP: 20
- SL: 15
- Final-observation exits: 13
- Average estimated cost: 0.513%
- Worst net trade: -7.58%
- Best net trade: +9.94%

## Walk-forward
TRAIN:
- N=28
- Average: +1.62%
- Sum: +45.34%
- Positive: 57.1%

BLIND:
- N=20
- Average: +2.32%
- Sum: +46.41%
- Positive: 60.0%

## Full-equity Diagnostic
- Start equity: 1000
- End equity: 2189.37
- Compound return: +118.94%
- Maximum drawdown: -30.72%

Full-equity compounding is diagnostic only and is not a sizing recommendation.

## Data Quality
Trade ID 43 passed the entry/cost selection but had only one price observation and no usable non-terminal price path after the >=90% terminal-anomaly guard.

It was explicitly excluded rather than silently removed.

## Interpretation
Exit tuning alone was insufficient on the unfiltered PAPER population.

Historical evidence indicates that the combination of:

`ACCEL <= -0.05`

and

`ESTIMATED_COST <= 2%`

materially separates the better historical entry population.

TP10/SL7 produced balanced TRAIN and BLIND performance.

This result is a candidate for further PAPER/shadow validation only.

No runtime, panel, admission, risk-authority, wallet, signing or live-trading behavior was changed.

Next analysis target: position sizing and portfolio drawdown.
