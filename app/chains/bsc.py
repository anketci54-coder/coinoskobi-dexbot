from web3 import Web3
from web3.providers import HTTPProvider
from web3.providers.base import BaseProvider

from app.config.settings import (
    RPC_URL,
    RPC_URL_SECONDARY,
)
from app.dex.provider_resilience import (
    classify_provider_failure,
)


_PROVIDER_FAILURES = {
    "TIMEOUT",
    "RATE_LIMIT",
    "CONNECTION",
    "SUBSCRIPTION",
}


class FailoverHTTPProvider(BaseProvider):
    """Primary-first HTTP RPC with one bounded secondary attempt."""

    def __init__(
        self,
        primary_url,
        secondary_url="",
        *,
        provider_factory=HTTPProvider,
    ):
        super().__init__()

        if not primary_url:
            raise ValueError("primary_url required")

        self.primary = provider_factory(primary_url)
        self.secondary = (
            provider_factory(secondary_url)
            if secondary_url
            else None
        )
        self.failover_count = 0
        self.last_provider = "PRIMARY"

    @staticmethod
    def _provider_error(response):
        if not isinstance(response, dict):
            return False

        error = response.get("error")
        if error is None:
            return False

        return (
            classify_provider_failure(error)
            in _PROVIDER_FAILURES
        )

    def make_request(self, method, params):
        try:
            response = self.primary.make_request(
                method,
                params,
            )

            if not self._provider_error(response):
                self.last_provider = "PRIMARY"
                return response

        except Exception:
            if self.secondary is None:
                raise
        else:
            if self.secondary is None:
                return response

        self.failover_count += 1
        self.last_provider = "SECONDARY"

        return self.secondary.make_request(
            method,
            params,
        )


def build_bsc_web3(
    primary_url=RPC_URL,
    secondary_url=RPC_URL_SECONDARY,
):
    provider = FailoverHTTPProvider(
        primary_url,
        secondary_url,
    )
    return Web3(provider)


w3 = build_bsc_web3()


def connect():
    return w3.is_connected()


def chain_id():
    return w3.eth.chain_id


def latest_block():
    return w3.eth.block_number
