# PAPER run boundaries

Preview a new run using the deployed application environment:

```sh
.venv/bin/python -m app.paper.run_boundary --db data/paper_trades.db --run-key corrected-paper-v1-20260927
```

Append `--apply` to commit the boundary. This command has no service control or
restart action. It requires an existing database, refuses any open position,
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
