# ---------------------------------------------------------------------------
# Risk signal thresholds
#
# These thresholds classify risk evidence.
# They DO NOT create trade authority by themselves.
#
# HARD_BLOCK remains owned by RiskGate and explicit critical evidence.
# ---------------------------------------------------------------------------

# Tax levels (%)
TAX_CAUTION_PERCENT = 10.0
TAX_HIGH_PERCENT = 20.0
TAX_EXTREME_PERCENT = 50.0

# Combined buy + sell tax
ROUND_TRIP_TAX_CAUTION_PERCENT = 15.0
ROUND_TRIP_TAX_HIGH_PERCENT = 30.0

# Severity labels
SEVERITY_NONE = "NONE"
SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"

# ---------------------------------------------------------------------------
# MEV / Sandwich exposure thresholds
#
# Pure classification only.
# No trade authority.
# No hard block.
# ---------------------------------------------------------------------------

# Trade size / pool liquidity ratio (%)
MEV_TRADE_LIQUIDITY_CAUTION_PERCENT = 0.50
MEV_TRADE_LIQUIDITY_HIGH_PERCENT = 1.00
MEV_TRADE_LIQUIDITY_CRITICAL_PERCENT = 3.00

# Expected price impact (%)
MEV_PRICE_IMPACT_CAUTION_PERCENT = 1.00
MEV_PRICE_IMPACT_HIGH_PERCENT = 3.00
MEV_PRICE_IMPACT_CRITICAL_PERCENT = 8.00

# Expected slippage (%)
MEV_SLIPPAGE_CAUTION_PERCENT = 1.00
MEV_SLIPPAGE_HIGH_PERCENT = 3.00
MEV_SLIPPAGE_CRITICAL_PERCENT = 8.00

# Shallow pool liquidity (USD)
MEV_LIQUIDITY_CAUTION_USD = 25_000
MEV_LIQUIDITY_HIGH_RISK_USD = 10_000

# ---------------------------------------------------------------------------
# MEV / Sandwich exposure thresholds
#
# Pure classification only.
# No trade authority.
# No hard block.
# ---------------------------------------------------------------------------

# Trade size / pool liquidity ratio (%)
MEV_TRADE_LIQUIDITY_CAUTION_PERCENT = 0.50
MEV_TRADE_LIQUIDITY_HIGH_PERCENT = 1.00
MEV_TRADE_LIQUIDITY_CRITICAL_PERCENT = 3.00

# Expected price impact (%)
MEV_PRICE_IMPACT_CAUTION_PERCENT = 1.00
MEV_PRICE_IMPACT_HIGH_PERCENT = 3.00
MEV_PRICE_IMPACT_CRITICAL_PERCENT = 8.00

# Expected slippage (%)
MEV_SLIPPAGE_CAUTION_PERCENT = 1.00
MEV_SLIPPAGE_HIGH_PERCENT = 3.00
MEV_SLIPPAGE_CRITICAL_PERCENT = 8.00

# Shallow pool liquidity (USD)
MEV_LIQUIDITY_CAUTION_USD = 25_000
MEV_LIQUIDITY_HIGH_RISK_USD = 10_000
