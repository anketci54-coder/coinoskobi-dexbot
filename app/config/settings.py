from dotenv import load_dotenv
import os

load_dotenv(".env")

APP_NAME = os.getenv("APP_NAME", "CoinoskobiDEX")
CHAIN = os.getenv("CHAIN", "bsc")
RPC_URL = os.getenv("RPC_URL", "")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Native DEX WSS runtime is enabled only when both
# WSS_URL and WSS_PAIR are explicitly configured.
WSS_URL = os.getenv("WSS_URL", "").strip()
WSS_PAIR = os.getenv("WSS_PAIR", "").strip()

# Optional target token for semantic native Swap decoding.
# Without it WSS lifecycle may run, but market/flow binding
# remains UNKNOWN rather than inventing token direction.
WSS_TOKEN = os.getenv("WSS_TOKEN", "").strip()
