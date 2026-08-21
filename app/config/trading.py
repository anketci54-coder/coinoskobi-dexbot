# ---------------------------------------------------------------------------
# Trading policy constants
# All numeric trading parameters are defined here.
# Import from this module; do not hardcode values elsewhere.
# ---------------------------------------------------------------------------

# --- Exit thresholds (as fractions, e.g. 0.20 = 20%) ---

# Close position when ROI reaches this level

# Close position when ROI falls to this level

# Trailing stop: close when price drops to (highest * TRAILING_STOP_FACTOR)

# --- Position sizing ---

# Default paper trade size in BNB

# Maximum concurrently OPEN paper positions.
# Aligned with one bounded Gecko multi-pool price request.
MAX_OPEN_PAPER_POSITIONS: int = 30

# TP price multiplier  (entry * TP_PRICE_MULTIPLIER)

# SL price multiplier  (entry * SL_PRICE_MULTIPLIER)

# --- Fee model ---

# Gas cost per trade leg (in BNB)

# Swap fee as a percentage of trade value (e.g. 0.25 = 0.25%)

# Buy / sell tax percentages (0 = unknown / not applicable)

# Slippage as a percentage of trade value

# MEV cost as a percentage of trade value

# --- Phase 4 position lifecycle policy ---
# Fractions of the original token position.
# These are mechanical defaults and may be calibrated later.
