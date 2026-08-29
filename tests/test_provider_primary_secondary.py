import asyncio

from app.chains.bsc import FailoverHTTPProvider
from app.dex.wss_failover import FailoverWSSRuntime


class FakeHTTPProvider:
    responses = {}
    calls = []

    def __init__(self, url):
        self.url = url

    def make_request(self, method, params):
        type(self).calls.append((self.url, method))
        result = type(self).responses[self.url]
        if isinstance(result, BaseException):
            raise result
        return result


def reset_http():
    FakeHTTPProvider.responses = {}
    FakeHTTPProvider.calls = []


def test_http_primary_success_does_not_touch_secondary():
    reset_http()
    FakeHTTPProvider.responses = {
        "primary": {"jsonrpc": "2.0", "id": 1, "result": "0x38"},
        "secondary": {"jsonrpc": "2.0", "id": 1, "result": "0x38"},
    }

    provider = FailoverHTTPProvider(
        "primary",
        "secondary",
        provider_factory=FakeHTTPProvider,
    )

    result = provider.make_request("eth_chainId", [])

    assert result["result"] == "0x38"
    assert FakeHTTPProvider.calls == [("primary", "eth_chainId")]
    assert provider.failover_count == 0
    assert provider.last_provider == "PRIMARY"


def test_http_rate_limit_uses_secondary_once():
    reset_http()
    FakeHTTPProvider.responses = {
        "primary": {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32005, "message": "limit exceeded"},
        },
        "secondary": {"jsonrpc": "2.0", "id": 1, "result": "0x38"},
    }

    provider = FailoverHTTPProvider(
        "primary",
        "secondary",
        provider_factory=FakeHTTPProvider,
    )

    result = provider.make_request("eth_chainId", [])

    assert result["result"] == "0x38"
    assert FakeHTTPProvider.calls == [
        ("primary", "eth_chainId"),
        ("secondary", "eth_chainId"),
    ]
    assert provider.failover_count == 1
    assert provider.last_provider == "SECONDARY"


def test_http_transport_failure_uses_secondary_once():
    reset_http()
    FakeHTTPProvider.responses = {
        "primary": ConnectionError("connection closed"),
        "secondary": {"jsonrpc": "2.0", "id": 1, "result": "0x38"},
    }

    provider = FailoverHTTPProvider(
        "primary",
        "secondary",
        provider_factory=FakeHTTPProvider,
    )

    result = provider.make_request("eth_chainId", [])

    assert result["result"] == "0x38"
    assert provider.failover_count == 1


class FakeWSSRuntime:
    statuses = {}
    urls = []

    def __init__(self, url, pair, **kwargs):
        self.url = url
        self.pair = pair
        self.stopped = False
        type(self).urls.append(url)

    async def run(self, max_events=None):
        return dict(type(self).statuses[self.url])

    def request_stop(self):
        self.stopped = True

    async def force_close(self):
        self.stopped = True
        return True

    def status(self):
        return dict(type(self).statuses[self.url])


def run(coro):
    return asyncio.run(coro)


def test_wss_primary_success_keeps_secondary_cold():
    FakeWSSRuntime.urls = []
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

    runtime = FailoverWSSRuntime(
        "wss://primary",
        "0xpair",
        fallback_url="wss://secondary",
        runtime_factory=FakeWSSRuntime,
    )

    result = run(runtime.run(max_events=1))

    assert FakeWSSRuntime.urls == ["wss://primary"]
    assert result["provider_role"] == "PRIMARY"
    assert result["provider_failover_count"] == 0


def test_wss_primary_failure_moves_to_secondary():
    FakeWSSRuntime.urls = []
    FakeWSSRuntime.statuses = {
        "wss://primary": {
            "state": "DISCONNECTED",
            "accepted_count": 0,
            "last_error": "ConnectionError: connection closed",
        },
        "wss://secondary": {
            "state": "DISCONNECTED",
            "accepted_count": 1,
            "last_error": None,
        },
    }

    runtime = FailoverWSSRuntime(
        "wss://primary",
        "0xpair",
        fallback_url="wss://secondary",
        runtime_factory=FakeWSSRuntime,
    )

    result = run(runtime.run(max_events=1))

    assert FakeWSSRuntime.urls == [
        "wss://primary",
        "wss://secondary",
    ]
    assert result["provider_role"] == "SECONDARY"
    assert result["provider_failover_count"] == 1
    assert result["secondary_configured"] is True
    assert result["execution_authority"] is False
