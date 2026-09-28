# PAPER run boundaries

Preview a new run using the deployed application environment:

```sh
.venv/bin/python -m app.paper.run_boundary --db data/paper_trades.db --run-key corrected-paper-v1-20260927
```

Append `--apply` to commit the boundary. This command has no service control or
restart action. It requires an existing database and, by default, refuses any open position,
and checks the boundary under a SQLite write transaction. A repeated active
run key is idempotent; a completed run key cannot be reused.

The command records the last trade, realization and candidate IDs, completes
the previous run record, and starts the standard 10,000 USDT PAPER run. It does
not delete or rewrite trades, realizations, balances or archival history.
Use it with the corrected application code deployed so new entries receive
their run attribution inside the insertion transaction.

Calibration requires the `corrected_paper_v1` admission marker, fresh exact-pool
USDT price provenance at admission, successful bound PHASE15H BUY and closing
SELL proofs, and proof for every partial realization. When a run is active,
only its attributed trades after the boundary qualify. Legacy rows remain in
history and accounting; missing proof is never manufactured during migration.

Creating a boundary does not calibrate the model: a clean run begins without
outcome samples. HOT observation sizing still requires verified LP protection
and the existing admission and execution gates.

## Legacy OPEN quarantine

A corrected run can explicitly preview legacy OPEN rows that cannot prove
current-model admission:

    .venv/bin/python -m app.paper.run_boundary --db data/paper_trades.db --run-key corrected-paper-v1-YYYYMMDD --quarantine-unproven-open

Preview remains read-only. Add `--apply` only after reviewing the returned
position IDs. The command refuses if even one OPEN row has valid
`corrected_paper_v1` admission, fresh exact-pool USDT provenance, and a
successful bound PHASE15H BUY proof.

On apply, qualifying legacy rows change from `OPEN` to `QUARANTINED` and an
audit row is written to `paper_position_quarantines`. Entry price, token
amount, realizations, PnL and close data are not rewritten or invented. The
quarantine and new run boundary share one SQLite write transaction, so a
concurrent entry cannot fall between the two operations.
