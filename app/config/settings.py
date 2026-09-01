from dotenv import load_dotenv
import os

load_dotenv(".env")

APP_NAME = os.getenv("APP_NAME", "CoinoskobiDEX")
CHAIN = os.getenv("CHAIN", "bsc")

RPC_URL = os.getenv("RPC_URL", "").strip()
RPC_URL_SECONDARY = os.getenv(
    "RPC_URL_SECONDARY",
    "",
).strip()
RPC_URL_TERTIARY = os.getenv(
    "RPC_URL_TERTIARY",
    "",
).strip()
RPC_URL_QUATERNARY = os.getenv(
    "RPC_URL_QUATERNARY",
    "",
).strip()

RPC_PROVIDER_COOLDOWN_SECONDS = max(
    1.0,
    float(
        os.getenv(
            "RPC_PROVIDER_COOLDOWN_SECONDS",
            "300",
        )
        or 300
    ),
)

PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Native DEX WSS runtime is enabled only when both
# WSS_URL and WSS_PAIR are explicitly configured.
WSS_URL = os.getenv("WSS_URL", "").strip()
WSS_URL_SECONDARY = os.getenv(
    "WSS_URL_SECONDARY",
    "",
).strip()
WSS_URL_TERTIARY = os.getenv(
    "WSS_URL_TERTIARY",
    "",
).strip()
WSS_URL_QUATERNARY = os.getenv(
    "WSS_URL_QUATERNARY",
    "",
).strip()
WSS_PAIR = os.getenv("WSS_PAIR", "").strip()

# Optional target token for semantic native Swap decoding.
# Without it WSS lifecycle may run, but market/flow binding
# remains UNKNOWN rather than inventing token direction.
WSS_TOKEN = os.getenv("WSS_TOKEN", "").strip()

# Full-universe observation stays fail-closed until deployment blocks are
# independently verified on the active BSC provider.
UNIVERSE_SHADOW_ENABLED = os.getenv(
    "UNIVERSE_SHADOW_ENABLED",
    "0",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

UNIVERSE_V2_START_BLOCK = int(
    os.getenv(
        "UNIVERSE_V2_START_BLOCK",
        "0",
    )
    or 0
)

UNIVERSE_V3_START_BLOCK = int(
    os.getenv(
        "UNIVERSE_V3_START_BLOCK",
        "0",
    )
    or 0
)
