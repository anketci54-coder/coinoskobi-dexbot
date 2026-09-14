# Trade Type Routing Migration Gate

Canonical rule: `control_mode != trade_type`.

This branch introduces runtime routing helpers but must not be merged until both integration points are wired and tested:

1. Every new paper trade passes through `canonicalize_trade_axes()` before insert.
2. Mathematical lifecycle selection uses `lifecycle_trade_type(position)` instead of `trade_policy`.
3. `control_mode` never selects a lifecycle engine.
4. Explicit invalid `trade_type` fails closed and must not silently fall back to legacy policy.
5. Legacy `trade_policy` remains compatibility-only until all producers and consumers are migrated.
6. No live wallet, signing, order-create, or execution authority is introduced.

This PR does not yet change NORMAL or VUR_KAC lifecycle behavior. Engine separation follows after routing is sealed.
