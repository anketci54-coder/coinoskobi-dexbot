import json
import threading
import time
from collections import OrderedDict

from web3.providers import HTTPProvider
from web3.providers.base import BaseProvider

from app.config.settings import (
    WSS_URL_SECONDARY,
    WSS_URL_TERTIARY,
    WSS_URL_QUATERNARY,
)
from app.dex.provider_resilience import (
    classify_provider_failure,
    provider_cooldown_seconds,
)
from app.dex.wss_runtime import (
    NativeWSSRuntime,
)


ROLES = (
    "PRIMARY",
    "SECONDARY",
    "TERTIARY",
    "QUATERNARY",
)

PROVIDER_FAILURES = {
    "TIMEOUT",
    "RATE_LIMIT",
    "QUOTA",
    "FORBIDDEN",
    "CONNECTION",
    "SUBSCRIPTION",
}

HEAVY_METHODS = {
    "eth_call",
    "eth_getCode",
    "eth_getLogs",
    "eth_getBlockByNumber",
    "eth_getTransactionByHash",
    "eth_getTransactionReceipt",
}

CACHE_TTLS = {
    "eth_chainId": 300.0,
    "net_version": 300.0,
    "web3_clientVersion": 300.0,
    "eth_getCode": 1.0,
    "eth_call": 0.10,
}

MAX_CACHE_ENTRIES = 1024


def _unique_urls(urls):
    result = []

    for value in urls:
        url = str(
            value or ""
        ).strip()

        if url and url not in result:
            result.append(url)

        if len(result) == len(ROLES):
            break

    return result


class ProviderBrokerHTTPProvider(
    BaseProvider
):
    """
    Quota-aware bounded BSC RPC broker.

    Provider URLs are never emitted from status().
    """

    def __init__(
        self,
        urls,
        *,
        provider_factory=HTTPProvider,
        cooldown_seconds=300.0,
        transient_cooldown_seconds=15.0,
        now_func=None,
        cache_ttls=None,
    ):
        super().__init__()

        self.cooldown_seconds = max(
            1.0,
            float(cooldown_seconds),
        )
        self.transient_cooldown_seconds = max(
            1.0,
            float(
                transient_cooldown_seconds
            ),
        )

        self._now = (
            now_func
            or time.monotonic
        )

        self._cache_ttls = dict(
            CACHE_TTLS
        )

        if cache_ttls:
            self._cache_ttls.update(
                cache_ttls
            )

        self._lock = (
            threading.RLock()
        )
        self._cache = OrderedDict()
        self._inflight = {}
        self._heavy_cursor = 0
        self._providers = []

        for index, url in enumerate(
            _unique_urls(urls)
        ):
            self._providers.append({
                "role": ROLES[index],
                "client": (
                    provider_factory(url)
                ),
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "circuit_opens": 0,
                "circuit_skips": 0,
                "last_failure": None,
                "cooldown_until": 0.0,
            })

        self.request_count = 0
        self.provider_attempt_count = 0
        self.failover_count = 0
        self.cache_hit_count = 0
        self.coalesced_wait_count = 0
        self.circuit_open_reject_count = 0
        self.last_provider = None

    @staticmethod
    def _response_failure(
        response,
    ):
        if (
            not isinstance(
                response,
                dict,
            )
            or response.get(
                "error"
            )
            is None
        ):
            return None

        failure = (
            classify_provider_failure(
                response["error"]
            )
        )

        return (
            failure
            if failure
            in PROVIDER_FAILURES
            else None
        )

    @staticmethod
    def _cache_key(
        method,
        params,
    ):
        try:
            encoded = json.dumps(
                params,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            encoded = repr(params)

        return (
            method,
            encoded,
        )

    def _cache_get(
        self,
        key,
        now,
    ):
        with self._lock:
            item = self._cache.get(
                key
            )

            if item is None:
                return None

            expires_at, response = (
                item
            )

            if expires_at <= now:
                self._cache.pop(
                    key,
                    None,
                )
                return None

            self._cache.move_to_end(
                key
            )
            self.cache_hit_count += 1

            return dict(response)

    def _cache_put(
        self,
        key,
        response,
        ttl,
        now,
    ):
        if (
            ttl <= 0
            or not isinstance(
                response,
                dict,
            )
            or response.get(
                "error"
            )
            is not None
            or "result"
            not in response
        ):
            return

        with self._lock:
            self._cache[key] = (
                now + ttl,
                dict(response),
            )

            self._cache.move_to_end(
                key
            )

            while (
                len(self._cache)
                > MAX_CACHE_ENTRIES
            ):
                self._cache.popitem(
                    last=False
                )

    def _candidate_indexes(
        self,
        method,
        now,
    ):
        with self._lock:
            healthy = []

            for index, item in enumerate(
                self._providers
            ):
                if (
                    item[
                        "cooldown_until"
                    ]
                    > now
                ):
                    item[
                        "circuit_skips"
                    ] += 1
                else:
                    healthy.append(
                        index
                    )

            if not healthy:
                self.circuit_open_reject_count += 1
                return []

            if (
                method
                not in HEAVY_METHODS
                or len(healthy) == 1
            ):
                return healthy

            start = (
                self._heavy_cursor
                % len(healthy)
            )
            self._heavy_cursor += 1

            return (
                healthy[start:]
                + healthy[:start]
            )

    def _mark_failure(
        self,
        item,
        failure,
        now,
    ):
        cooldown = (
            provider_cooldown_seconds(
                failure,
                quota_seconds=(
                    self.cooldown_seconds
                ),
                transient_seconds=(
                    self.transient_cooldown_seconds
                ),
            )
        )

        with self._lock:
            item["failures"] += 1
            item[
                "last_failure"
            ] = failure

            if cooldown > 0:
                item[
                    "cooldown_until"
                ] = max(
                    item[
                        "cooldown_until"
                    ],
                    now + cooldown,
                )
                item[
                    "circuit_opens"
                ] += 1

    def _mark_success(
        self,
        item,
    ):
        with self._lock:
            item["successes"] += 1
            item[
                "last_failure"
            ] = None
            item[
                "cooldown_until"
            ] = 0.0

    def _request_uncached(
        self,
        method,
        params,
    ):
        now = self._now()

        indexes = (
            self._candidate_indexes(
                method,
                now,
            )
        )

        if not indexes:
            raise ConnectionError(
                "all configured RPC provider circuits are open"
            )

        last_exception = None
        last_response = None

        for position, index in enumerate(
            indexes
        ):
            item = self._providers[
                index
            ]

            with self._lock:
                self.last_provider = (
                    item["role"]
                )
                self.provider_attempt_count += 1
                item[
                    "requests"
                ] += 1

            try:
                response = (
                    item["client"]
                    .make_request(
                        method,
                        params,
                    )
                )

            except Exception as exc:
                failure = (
                    classify_provider_failure(
                        exc
                    )
                )

                if (
                    failure
                    not in
                    PROVIDER_FAILURES
                ):
                    raise

                self._mark_failure(
                    item,
                    failure,
                    now,
                )
                last_exception = exc

            else:
                failure = (
                    self._response_failure(
                        response
                    )
                )

                if failure is None:
                    self._mark_success(
                        item
                    )
                    return response

                self._mark_failure(
                    item,
                    failure,
                    now,
                )
                last_response = response

            if (
                position + 1
                < len(indexes)
            ):
                with self._lock:
                    self.failover_count += 1
                continue

            if last_response is not None:
                return last_response

            if last_exception is not None:
                raise last_exception

        raise ConnectionError(
            "RPC provider broker exhausted"
        )

    def make_request(
        self,
        method,
        params,
    ):
        with self._lock:
            self.request_count += 1

        ttl = max(
            0.0,
            float(
                self._cache_ttls.get(
                    method,
                    0.0,
                )
            ),
        )

        if ttl <= 0:
            return (
                self._request_uncached(
                    method,
                    params,
                )
            )

        key = self._cache_key(
            method,
            params,
        )

        cached = self._cache_get(
            key,
            self._now(),
        )

        if cached is not None:
            return cached

        with self._lock:
            event = (
                self._inflight.get(
                    key
                )
            )

            if event is None:
                event = (
                    threading.Event()
                )
                self._inflight[
                    key
                ] = event
                leader = True
            else:
                self.coalesced_wait_count += 1
                leader = False

        if not leader:
            event.wait(
                timeout=2.0
            )

            cached = (
                self._cache_get(
                    key,
                    self._now(),
                )
            )

            if cached is not None:
                return cached

            return (
                self._request_uncached(
                    method,
                    params,
                )
            )

        try:
            response = (
                self._request_uncached(
                    method,
                    params,
                )
            )

            self._cache_put(
                key,
                response,
                ttl,
                self._now(),
            )

            return response

        finally:
            with self._lock:
                current = (
                    self._inflight.pop(
                        key,
                        None,
                    )
                )

                if current is not None:
                    current.set()

    def status(self):
        now = self._now()

        with self._lock:
            providers = [
                {
                    "role": (
                        item["role"]
                    ),
                    "requests": (
                        item["requests"]
                    ),
                    "successes": (
                        item["successes"]
                    ),
                    "failures": (
                        item["failures"]
                    ),
                    "circuit_opens": (
                        item[
                            "circuit_opens"
                        ]
                    ),
                    "circuit_skips": (
                        item[
                            "circuit_skips"
                        ]
                    ),
                    "circuit_open": (
                        item[
                            "cooldown_until"
                        ]
                        > now
                    ),
                    "last_failure": (
                        item[
                            "last_failure"
                        ]
                    ),
                }
                for item
                in self._providers
            ]

            return {
                "state": (
                    "READY"
                    if self._providers
                    else "UNCONFIGURED"
                ),
                "provider_count": (
                    len(
                        self._providers
                    )
                ),
                "last_provider": (
                    self.last_provider
                ),
                "request_count": (
                    self.request_count
                ),
                "provider_attempt_count": (
                    self.provider_attempt_count
                ),
                "failover_count": (
                    self.failover_count
                ),
                "cache_hit_count": (
                    self.cache_hit_count
                ),
                "coalesced_wait_count": (
                    self.coalesced_wait_count
                ),
                "circuit_open_reject_count": (
                    self.circuit_open_reject_count
                ),
                "providers": providers,
                "secret_logging_allowed": False,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            }


class ProviderBrokerWSSRuntime:
    """
    Bounded primary-first WSS broker
    for up to four providers.
    """

    def __init__(
        self,
        url,
        pair,
        *,
        provider_urls=None,
        runtime_factory=NativeWSSRuntime,
        **runtime_kwargs,
    ):
        if not url:
            raise ValueError(
                "url required"
            )

        if not pair:
            raise ValueError(
                "pair required"
            )

        fallbacks = (
            [
                WSS_URL_SECONDARY,
                WSS_URL_TERTIARY,
                WSS_URL_QUATERNARY,
            ]
            if provider_urls is None
            else list(
                provider_urls
            )
        )

        self._urls = _unique_urls(
            [
                url,
                *fallbacks,
            ]
        )

        self.pair = pair
        self.runtime_factory = (
            runtime_factory
        )
        self.runtime_kwargs = dict(
            runtime_kwargs
        )

        if len(self._urls) > 1:
            self.runtime_kwargs.setdefault(
                "max_reconnects",
                1,
            )

        self._runtime = None
        self._stop = False
        self.active_provider = (
            "PRIMARY"
        )
        self.failover_count = 0
        self.last_error = None
        self.last_status = None

    def request_stop(self):
        self._stop = True

        if self._runtime is not None:
            self._runtime.request_stop()

    async def force_close(self):
        self.request_stop()

        if self._runtime is None:
            return False

        close = getattr(
            self._runtime,
            "force_close",
            None,
        )

        if close is None:
            return False

        return await close()

    async def run(
        self,
        max_events=None,
    ):
        remaining = max_events

        for index, url in enumerate(
            self._urls
        ):
            if self._stop:
                break

            self.active_provider = (
                ROLES[index]
            )

            runtime = (
                self.runtime_factory(
                    url,
                    self.pair,
                    **self.runtime_kwargs,
                )
            )
            self._runtime = runtime

            status = await runtime.run(
                max_events=remaining
            )

            self.last_status = status
            self.last_error = (
                status.get(
                    "last_error"
                )
            )

            if self._stop:
                break

            if max_events is not None:
                accepted = int(
                    status.get(
                        "accepted_count",
                        0,
                    )
                    or 0
                )

                remaining = max(
                    0,
                    int(remaining)
                    - accepted,
                )

                if remaining == 0:
                    break

            if not self.last_error:
                break

            if (
                index + 1
                < len(self._urls)
            ):
                self.failover_count += 1
                continue

            break

        self._runtime = None

        return self.status()

    def status(self):
        base = (
            self._runtime.status()
            if self._runtime
            is not None
            else dict(
                self.last_status
                or {}
            )
        )

        base.update({
            "provider_role": (
                self.active_provider
            ),
            "provider_count": (
                len(self._urls)
            ),
            "provider_failover_count": (
                self.failover_count
            ),
            "secondary_configured": (
                len(self._urls) > 1
            ),
            "last_error": (
                self.last_error
            ),
            "secret_logging_allowed": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        })

        return base
