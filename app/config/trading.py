# ---------------------------------------------------------------------------
# Trading policy constants
# All numeric trading parameters are defined here.
# Import from this module; do not hardcode values elsewhere.
# ---------------------------------------------------------------------------

# --- Exit thresholds (as fractions, e.g. 0.20 = 20%) ---

# Close position when ROI reaches this level
TAKE_PROFIT: float = 0.20

# Close position when ROI falls to this level
STOP_LOSS: float = -0.10

# Trailing stop: close when price drops to (highest * TRAILING_STOP_FACTOR)
TRAILING_STOP_FACTOR: float = 0.90

# --- Position sizing ---

# Default paper trade size in BNB
DEFAULT_AMOUNT_BNB: float = 0.01

# Maximum concurrently OPEN paper positions.
# Aligned with one bounded Gecko multi-pool price request.
MAX_OPEN_PAPER_POSITIONS: int = 30

# TP price multiplier  (entry * TP_PRICE_MULTIPLIER)
TP_PRICE_MULTIPLIER: float = 1.20

# SL price multiplier  (entry * SL_PRICE_MULTIPLIER)
SL_PRICE_MULTIPLIER: float = 0.90

# --- Fee model ---

# Gas cost per trade leg (in BNB)
DEFAULT_GAS_BUY:  float = 0.00018
DEFAULT_GAS_SELL: float = 0.00018

# Swap fee as a percentage of trade value (e.g. 0.25 = 0.25%)
DEFAULT_SWAP_FEE: float = 0.25

# Buy / sell tax percentages (0 = unknown / not applicable)
DEFAULT_BUY_TAX:  float = 0.0
DEFAULT_SELL_TAX: float = 0.0

# Slippage as a percentage of trade value
DEFAULT_SLIPPAGE: float = 0.5

# MEV cost as a percentage of trade value
DEFAULT_MEV_COST: float = 0.2

# --- Phase 4 position lifecycle policy ---
# Fractions of the original token position.
# These are mechanical defaults and may be calibrated later.

TP1_ROI: float = 0.20
TP1_CLOSE_FRACTION: float = 0.20

TP2_ROI: float = 0.50
TP2_CLOSE_FRACTION: float = 0.25

TP3_ROI: float = 1.00
TP3_CLOSE_FRACTION: float = 0.25

RUNNER_FRACTION: float = 0.30
