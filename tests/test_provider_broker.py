import asyncio

import pytest

from app.dex.provider_broker import (
    ProviderBrokerHTTPProvider,
    ProviderBrokerWSSRuntime,
)
from app.dex.provider_resilience import (
    classify_provider_failure,
)


class FakeHTTPProvider:
    responses = {}
    calls = []

    def __init__(self, url):
        self.url = url

    def make_request(
        self,
        method,
        params,
    ):
        type(self).calls.append(
            (
                self.url,
                method,
                params,
            )
        )

        result = (
            type(self).responses[
                self.url
            ]
        )

        if isinstance(
            result,
            BaseException,
        ):
            raise result

        if callable(result):
            return result(
                method,
                params,
            )

        return dict(result)


def reset_http():
    FakeHTTPProvider.responses = {}
    FakeHTTPProvider.calls = []


def broker(
    *urls,
    **kwargs,
):
    return (
        ProviderBrokerHTTPProvider(
            list(urls),
            provider_factory=(
                FakeHTTPProvider
            ),
            now_func=(
                lambda: 100.0
            ),
            **kwargs,
        )
    )


def test_primary_success_is_cached_without_secondary_call():
    reset_http()

    FakeHTTPProvider.responses = {
        "secret-primary": {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x38",
        },
        "secret-secondary": {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x38",
        },
    }

    provider = broker(
        "secret-primary",
        "secret-secondary",
    )

    assert provider.make_request(
        "eth_chainId",
        [],
    )["result"] == "0x38"

    assert provider.make_request(
        "eth_chainId",
        [],
    )["result"] == "0x38"

    assert (
        FakeHTTPProvider.calls
        == [
            (
                "secret-primary",
                "eth_chainId",
                [],
            ),
        ]
    )

    status = provider.status()

    assert (
        status[
            "cache_hit_count"
        ]
        == 1
    )
    assert (
        "secret-primary"
        not in str(status)
    )
    assert (
        "secret-secondary"
        not in str(status)
    )
    assert (
        status[
            "execution_authority"
        ]
        is False
    )


def test_rate_limit_opens_circuit_and_skips_primary():
    reset_http()

    FakeHTTPProvider.responses = {
        "primary": {
            "error": {
                "code": -32005,
                "message": (
                    "limit exceeded"
                ),
            },
        },
        "secondary": {
            "result": "0x38",
        },
    }

    provider = broker(
        "primary",
        "secondary",
        cache_ttls={
            "eth_chainId": 0.0,
        },
    )

    assert provider.make_request(
        "eth_chainId",
        [],
    )["result"] == "0x38"

    assert (
        FakeHTTPProvider.calls
        == [
            (
                "primary",
                "eth_chainId",
                [],
            ),
            (
                "secondary",
                "eth_chainId",
                [],
            ),
        ]
    )

    FakeHTTPProvider.calls = []

    assert provider.make_request(
        "eth_chainId",
        [],
    )["result"] == "0x38"

    assert (
        FakeHTTPProvider.calls
        == [
            (
                "secondary",
                "eth_chainId",
                [],
            ),
        ]
    )

    status = provider.status()

    assert (
        status[
            "failover_count"
        ]
        == 1
    )
    assert (
        status["providers"][0][
            "circuit_open"
        ]
        is True
    )
    assert (
        status["providers"][0][
            "last_failure"
        ]
        == "RATE_LIMIT"
    )


def test_all_open_circuits_fail_fast_without_new_rpc_calls():
    reset_http()

    limited = {
        "error": {
            "code": -32005,
            "message": (
                "limit exceeded"
            ),
        },
    }

    FakeHTTPProvider.responses = {
        "primary": limited,
        "secondary": limited,
    }

    provider = broker(
        "primary",
        "secondary",
        cache_ttls={
            "eth_chainId": 0.0,
        },
    )

    assert (
        "error"
        in provider.make_request(
            "eth_chainId",
            [],
        )
    )

    calls_before = list(
        FakeHTTPProvider.calls
    )

    with pytest.raises(
        ConnectionError
    ):
        provider.make_request(
            "eth_chainId",
            [],
        )

    assert (
        FakeHTTPProvider.calls
        == calls_before
    )

    assert (
        provider.status()[
            "circuit_open_reject_count"
        ]
        == 1
    )


def test_heavy_methods_rotate_across_available_providers():
    reset_http()

    FakeHTTPProvider.responses = {
        "primary": {
            "result": "0x1",
        },
        "secondary": {
            "result": "0x2",
        },
        "tertiary": {
            "result": "0x3",
        },
    }

    provider = broker(
        "primary",
        "secondary",
        "tertiary",
        cache_ttls={
            "eth_call": 0.0,
        },
    )

    for index in range(3):
        provider.make_request(
            "eth_call",
            [
                {
                    "to": (
                        f"0x{index:040x}"
                    ),
                }
            ],
        )

    assert [
        row[0]
        for row
        in FakeHTTPProvider.calls
    ] == [
        "primary",
        "secondary",
        "tertiary",
    ]


def test_provider_failure_classifier_covers_real_limit_shapes():
    assert (
        classify_provider_failure(
            "HTTP Error 429: Too Many Requests"
        )
        == "RATE_LIMIT"
    )

    assert (
        classify_provider_failure(
            "HTTP Error 403: Forbidden"
        )
        == "FORBIDDEN"
    )

    assert (
        classify_provider_failure(
            "credits exhausted"
        )
        == "QUOTA"
    )


class FakeWSSRuntime:
    statuses = {}
    urls = []
    kwargs = []

    def __init__(
        self,
        url,
        pair,
        **kwargs,
    ):
        self.url = url
        self.pair = pair

        type(self).urls.append(
            url
        )
        type(self).kwargs.append(
            dict(kwargs)
        )

    async def run(
        self,
        max_events=None,
    ):
        return dict(
            type(self).statuses[
                self.url
            ]
        )

    def request_stop(self):
        return None

    async def force_close(self):
        return True

    def status(self):
        return dict(
            type(self).statuses[
                self.url
            ]
        )


def run(coro):
    return asyncio.run(coro)


def test_wss_broker_uses_bounded_multi_provider_failover():
    FakeWSSRuntime.urls = []
    FakeWSSRuntime.kwargs = []

    FakeWSSRuntime.statuses = {
        "wss://primary": {
            "state": "DISCONNECTED",
            "accepted_count": 0,
            "last_error": (
                "connection closed"
            ),
        },
        "wss://secondary": {
            "state": "DISCONNECTED",
            "accepted_count": 0,
            "last_error": (
                "rate limit"
            ),
        },
        "wss://tertiary": {
            "state": "DISCONNECTED",
            "accepted_count": 1,
            "last_error": None,
        },
    }

    runtime = (
        ProviderBrokerWSSRuntime(
            "wss://primary",
            "0xpair",
            provider_urls=[
                "wss://secondary",
                "wss://tertiary",
            ],
            runtime_factory=(
                FakeWSSRuntime
            ),
        )
    )

    result = run(
        runtime.run(
            max_events=1
        )
    )

    assert (
        FakeWSSRuntime.urls
        == [
            "wss://primary",
            "wss://secondary",
            "wss://tertiary",
        ]
    )

    assert all(
        row["max_reconnects"]
        == 1
        for row
        in FakeWSSRuntime.kwargs
    )

    assert (
        result[
            "provider_role"
        ]
        == "TERTIARY"
    )
    assert (
        result[
            "provider_failover_count"
        ]
        == 2
    )
    assert (
        result[
            "provider_count"
        ]
        == 3
    )
    assert (
        result[
            "execution_authority"
        ]
        is False
    )


def test_wss_primary_success_keeps_fallbacks_cold():
    FakeWSSRuntime.urls = []
    FakeWSSRuntime.kwargs = []

    FakeWSSRuntime.statuses = {
        "wss://primary": {
            "state": "DISCONNECTED",
            "accepted_count": 1,
            "last_error": None,
        },
        "wss://secondary": {
            "state": "DISCONNECTED",
            "accepted_count": 1,
            "last_error": None,
        },
    }

    runtime = (
        ProviderBrokerWSSRuntime(
            "wss://primary",
            "0xpair",
            provider_urls=[
                "wss://secondary",
            ],
            runtime_factory=(
                FakeWSSRuntime
            ),
        )
    )

    result = run(
        runtime.run(
            max_events=1
        )
    )

    assert (
        FakeWSSRuntime.urls
        == [
            "wss://primary",
        ]
    )
    assert (
        result[
            "provider_role"
        ]
        == "PRIMARY"
    )
    assert (
        result[
            "provider_failover_count"
        ]
        == 0
    )
