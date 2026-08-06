from dotenv import load_dotenv
import os

load_dotenv(".env")

APP_NAME = os.getenv("APP_NAME", "CoinoskobiDEX")
CHAIN = os.getenv("CHAIN", "bsc")
RPC_URL = os.getenv("RPC_URL", "")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
