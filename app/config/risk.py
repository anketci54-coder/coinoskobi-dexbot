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
