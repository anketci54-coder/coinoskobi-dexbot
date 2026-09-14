# Trade Type Routing Migration Gate

Canonical rule: `control_mode != trade_type`.

PR #153 establishes the canonical write contract and routing helper without changing PaperManager lifecycle behavior yet.

1. Every new paper trade passes through `canonicalize_trade_axes()` before insert.
2. `lifecycle_trade_type(position)` defines canonical routing precedence: explicit `trade_type` first, legacy `trade_policy` only as compatibility fallback.
3. `control_mode` never selects a lifecycle engine.
4. Explicit invalid `control_mode` or `trade_type` fails closed.
5. Legacy `trade_policy` remains compatibility-only until all producers and consumers are migrated.
6. No live wallet, signing, order-create, or execution authority is introduced.

The next PR wires PaperManager mathematical lifecycle selection to `lifecycle_trade_type(position)`. NORMAL/VUR_KAC lifecycle behavior itself remains unchanged until the dedicated engine-separation PR.
