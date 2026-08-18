# ---------------------------------------------------------------------------
# Trading policy constants
# Numeric values here are infrastructure/default cost inputs only.
# Entry, sizing, SL, profit protection and runner exits are calculated by
# the runtime models; this module carries no static TP/SL/trailing authority.
# ---------------------------------------------------------------------------

# --- Position sizing ---

# Legacy paper amount retained only for old-account compatibility.
DEFAULT_AMOUNT_BNB: float = 0.01

# Maximum concurrently OPEN paper positions.
# Aligned with one bounded Gecko multi-pool price request.
MAX_OPEN_PAPER_POSITIONS: int = 30

# --- Fee model defaults ---
# These are fallback accounting inputs, not execution-quality approval.

DEFAULT_GAS_BUY: float = 0.00018
DEFAULT_GAS_SELL: float = 0.00018
DEFAULT_SWAP_FEE: float = 0.25
DEFAULT_BUY_TAX: float = 0.0
DEFAULT_SELL_TAX: float = 0.0
DEFAULT_SLIPPAGE: float = 0.5
DEFAULT_MEV_COST: float = 0.2
