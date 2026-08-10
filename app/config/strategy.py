# ---------------------------------------------------------------------------
# Strategy policy constants
#
# Faz 3 ilkesi:
# - karar anlamini degistirme
# - mevcut hard-coded esikleri config'e tasi
# - threshold degisikligi kod degisikligi gerektirmesin
# ---------------------------------------------------------------------------

# ERC20
SCORE_ERC20_OK = 5

# Pair
SCORE_PAIR_EXISTS = 20
SCORE_QUOTE_OK = 15

# Contract size thresholds
CONTRACT_SIZE_LARGE = 6000
CONTRACT_SIZE_OK = 3000
CONTRACT_SIZE_SMALL = 1500

SCORE_CONTRACT_LARGE = 20
SCORE_CONTRACT_OK = 15
SCORE_CONTRACT_SMALL = 10

# Owner
SCORE_OWNER_NONE = 10
SCORE_OWNER_RENOUNCED = 8

# Mint
SCORE_MINT_NONE = 15
PENALTY_MINT_ENABLED = 30

# Pause
SCORE_PAUSE_NONE = 5
PENALTY_PAUSE_ENABLED = 10

# Blacklist
SCORE_BLACKLIST_NONE = 5
PENALTY_BLACKLIST_ENABLED = 15

# Limits
SCORE_MAX_TX_NONE = 5
SCORE_MAX_WALLET_NONE = 5

# Decision thresholds
PAPER_BUY_SCORE = 90
WATCH_SCORE = 70
