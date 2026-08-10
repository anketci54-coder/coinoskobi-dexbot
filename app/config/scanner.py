"""
Coinoskobi Scanner Ayarları

Bu dosyadaki değerler scanner davranışını belirler.
Kod değiştirmeden sadece buradaki eşikler güncellenebilir.
"""

# Desteklenen ağ
NETWORK = "bsc"

# Ana veri kaynağı
SCANNER_SOURCE = "geckoterminal"

# Likidite (USD)
MIN_LIQUIDITY_USD = 5000

# Son 24 saat hacim (USD)
MIN_VOLUME_24H_USD = 1000

# Son 24 saat minimum alış
MIN_BUYS_24H = 5

# Havuz yaşı (saat)
MAX_POOL_AGE_HOURS = 48

# Minimum FDV
MIN_FDV_USD = 5000

# Maksimum FDV
MAX_FDV_USD = 100000000

# Desteklenen DEX'ler
ALLOWED_DEX = [
    "pancakeswap_v2",
    "pancakeswap_v3",
    "four-meme"
]

# Admission queue kapasitesi.
# Deep-analysis sınırı değildir; bekleyen aday havuzudur.
MAX_PENDING_CANDIDATES = 100000

# Aynı token analiz edildikten sonra hemen tekrar RPC'ye girmesin.
RECENT_ANALYSIS_COOLDOWN_SECONDS = 20

# Pahali analyzer isleri icin bounded worker havuzu.
ANALYZER_WORKERS = 8

# Cache satırı maksimum yaşı (dakika)
# Scanner/runner döngüsüne toleranslı olacak şekilde 15 dk.
CACHE_MAX_AGE_MINUTES = 15

# Analyzer cache TTL
TOKEN_ANALYZER_CACHE_TTL_SECONDS = 30
PAIR_ANALYZER_CACHE_TTL_SECONDS = 15
RISK_ANALYZER_CACHE_TTL_SECONDS = 30

# HTTP timeout
HTTP_TIMEOUT = 20

# İstekler arası bekleme (sn)
REQUEST_DELAY = 0.15

# Scanner log
DEBUG = True
