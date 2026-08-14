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
# Unified Score v1
#
# This is NOT probability.
# This is NOT trade authority.
#
# Legacy StrategyEngine already includes:
# - ERC20 / pair / quote
# - bytecode size
# - owner
# - mint
# - pause
# - blacklist
# - maxTx / maxWallet safe bonuses
#
# Therefore Unified Score v1 MUST NOT punish those same
# contract-control signals again.
#
# v1 only adds dimensions not already represented:
# - tax / round-trip tax
# - MEV / sandwich exposure
# ---------------------------------------------------------------------------

UNIFIED_STRATEGY_MAX_RAW_SCORE = 105.0

UNIFIED_TAX_PENALTY_LOW = 1.0
UNIFIED_TAX_PENALTY_MEDIUM = 3.0
UNIFIED_TAX_PENALTY_HIGH = 8.0
UNIFIED_TAX_PENALTY_CRITICAL = 15.0

UNIFIED_MEV_PENALTY_LOW = 1.0
UNIFIED_MEV_PENALTY_MEDIUM = 3.0
UNIFIED_MEV_PENALTY_HIGH = 8.0
UNIFIED_MEV_PENALTY_CRITICAL = 15.0

# Confidence / evidence coverage.
#
# Unknown evidence lowers confidence only.
# It does NOT create a score penalty.
UNIFIED_CONFIDENCE_STRATEGY_WEIGHT = 40.0
UNIFIED_CONFIDENCE_SELLABILITY_WEIGHT = 20.0
UNIFIED_CONFIDENCE_TAX_WEIGHT = 20.0
UNIFIED_CONFIDENCE_MEV_WEIGHT = 20.0

# ---------------------------------------------------------------------------
# Unified Decision Contract v1
#
# Advisory / paper-candidate contract only.
#
# Does NOT have:
# - live trade authority
# - wallet authority
# - execution authority
#
# Execution cost and Entry/SL/TP are evaluated later.
# ---------------------------------------------------------------------------

UNIFIED_DECISION_PAPER_SCORE = 90.0
UNIFIED_DECISION_WATCH_SCORE = 70.0

# Minimum evidence coverage for PAPER observation.
# Strategy + real market/MEV evidence is sufficient for paper learning.
# Missing sellability/tax remains UNKNOWN in opening context.
# This grants no live, wallet or execution authority.
UNIFIED_DECISION_MIN_CONFIDENCE = 60.0

