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
