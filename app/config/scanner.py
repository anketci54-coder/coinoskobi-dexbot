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

# RPC doğrulamasına gönderilecek maksimum aday
MAX_RPC_CANDIDATES = 30

# HTTP timeout
HTTP_TIMEOUT = 20

# İstekler arası bekleme (sn)
REQUEST_DELAY = 0.15

# Scanner log
DEBUG = True
