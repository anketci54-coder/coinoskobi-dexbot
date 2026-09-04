from web3 import Web3

from app.config.settings import (
    RPC_URL,
    RPC_URL_SECONDARY,
    RPC_URL_TERTIARY,
    RPC_URL_QUATERNARY,
    RPC_PROVIDER_COOLDOWN_SECONDS,
)
from app.dex.provider_broker import (
    ProviderBrokerHTTPProvider,
)
from app.dex.provider_public_fallback import (
    ReadOnlyPublicFallbackProvider,
)


def build_bsc_web3(
    primary_url=RPC_URL,
    secondary_url=RPC_URL_SECONDARY,
    tertiary_url=RPC_URL_TERTIARY,
    quaternary_url=RPC_URL_QUATERNARY,
    *,
    cooldown_seconds=(
        RPC_PROVIDER_COOLDOWN_SECONDS
    ),
    public_fallback_enabled=True,
    public_urls=None,
):
    private_provider = (
        ProviderBrokerHTTPProvider(
            [
                primary_url,
                secondary_url,
                tertiary_url,
                quaternary_url,
            ],
            cooldown_seconds=(
                cooldown_seconds
            ),
        )
    )

    provider = ReadOnlyPublicFallbackProvider(
        private_provider,
        enabled=public_fallback_enabled,
        public_urls=public_urls,
    )

    return Web3(provider)


w3 = build_bsc_web3()


def connect():
    return w3.is_connected()


def chain_id():
    return w3.eth.chain_id


def latest_block():
    return w3.eth.block_number
