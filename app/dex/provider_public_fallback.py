from __future__ import annotations

import threading
import time
from typing import Any

from web3.providers import HTTPProvider
from web3.providers.base import BaseProvider


OFFICIAL_BNB_PUBLIC_RPC_URLS = (
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-dataseed-public.bnbchain.org",
)

# Official BNB public endpoints explicitly do not provide eth_getLogs.
# Keep the emergency path narrowly read-only and method allowlisted.
PUBLIC_READ_METHODS = {
    "eth_call",
    "eth_getCode",
    "eth_getBalance",
    "eth_chainId",
    "eth_blockNumber",
    "eth_getTransactionByHash",
    "eth_getTransactionReceipt",
    "net_version",
    "web3_clientVersion",
}


def _response_ok(response: Any) -> bool:
    return (
        isinstance(response, dict)
        and response.get("error") is None
        and "result" in response
    )


class ReadOnlyPublicFallbackProvider(BaseProvider):
    """
    Wrap the configured private RPC broker with a bounded official-BNB
    emergency fallback for read-only methods only.

    The fallback never handles eth_getLogs, transaction submission,
    signing, wallet operations, or any execution authority.
    """

    def __init__(
        self,
        primary_provider: BaseProvider,
        *,
        enabled: bool = True,
        public_urls=None,
        provider_factory=HTTPProvider,
        cooldown_seconds: float = 15.0,
        now_func=None,
    ):
        super().__init__()
        self.primary_provider = primary_provider
        self.enabled = bool(enabled)
        self.cooldown_seconds = max(1.0, float(cooldown_seconds))
        self._now = now_func or time.monotonic
        self._lock = threading.RLock()
        self._cursor = 0
        self._providers = []

        if self.enabled:
            seen = set()
            for url in (public_urls or OFFICIAL_BNB_PUBLIC_RPC_URLS):
                value = str(url or "").strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                self._providers.append({
                    "client": provider_factory(value),
                    "requests": 0,
                    "successes": 0,
                    "failures": 0,
                    "cooldown_until": 0.0,
                })

        self.private_failures = 0
        self.public_attempts = 0
        self.public_successes = 0
        self.public_failures = 0
        self.public_skips = 0
        self.last_source = "PRIVATE"

    def _public_candidates(self, now: float):
        with self._lock:
            healthy = [
                index
                for index, item in enumerate(self._providers)
                if float(item["cooldown_until"]) <= now
            ]
            if not healthy:
                return []
            start = self._cursor % len(healthy)
            self._cursor += 1
            return healthy[start:] + healthy[:start]

    def _try_public(self, method, params):
        now = self._now()
        indexes = self._public_candidates(now)

        for index in indexes:
            item = self._providers[index]
            with self._lock:
                item["requests"] += 1
                self.public_attempts += 1

            try:
                response = item["client"].make_request(method, params)
            except Exception:
                response = None

            if _response_ok(response):
                with self._lock:
                    item["successes"] += 1
                    item["cooldown_until"] = 0.0
                    self.public_successes += 1
                    self.last_source = "OFFICIAL_BNB_PUBLIC"
                return response

            with self._lock:
                item["failures"] += 1
                item["cooldown_until"] = now + self.cooldown_seconds
                self.public_failures += 1

        return None

    def make_request(self, method, params):
        private_response = None
        private_exception = None

        try:
            private_response = self.primary_provider.make_request(method, params)
            if _response_ok(private_response):
                with self._lock:
                    self.last_source = "PRIVATE"
                return private_response
        except Exception as exc:
            private_exception = exc

        with self._lock:
            self.private_failures += 1

        if (
            not self.enabled
            or method not in PUBLIC_READ_METHODS
            or not self._providers
        ):
            with self._lock:
                self.public_skips += 1
            if private_exception is not None:
                raise private_exception
            return private_response

        public_response = self._try_public(method, params)
        if public_response is not None:
            return public_response

        if private_exception is not None:
            raise private_exception
        return private_response

    def status(self):
        private_status = getattr(self.primary_provider, "status", None)
        private = private_status() if callable(private_status) else {}
        now = self._now()

        with self._lock:
            public = [
                {
                    "role": f"OFFICIAL_BNB_PUBLIC_{index + 1}",
                    "requests": item["requests"],
                    "successes": item["successes"],
                    "failures": item["failures"],
                    "circuit_open": float(item["cooldown_until"]) > now,
                }
                for index, item in enumerate(self._providers)
            ]
            return {
                "state": "READY" if private or public else "UNCONFIGURED",
                "private": private,
                "public_fallback_enabled": self.enabled,
                "public_provider_count": len(public),
                "public_attempts": self.public_attempts,
                "public_successes": self.public_successes,
                "public_failures": self.public_failures,
                "public_skips": self.public_skips,
                "private_failures": self.private_failures,
                "last_source": self.last_source,
                "public_providers": public,
                "eth_getLogs_public_fallback": False,
                "transaction_submission_public_fallback": False,
                "secret_logging_allowed": False,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "signing_authority": False,
                "execution_authority": False,
            }
