import pytest

from app.dex.provider_public_fallback import ReadOnlyPublicFallbackProvider


class PrivateProvider:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def make_request(self, method, params):
        self.calls.append(method)
        if self.error:
            raise self.error
        return self.response

    def status(self):
        return {"provider_count": 4, "providers": []}


class PublicProvider:
    def __init__(self, url, response=None):
        self.url = url
        self.response = response or {"jsonrpc": "2.0", "id": 1, "result": "0x38"}
        self.calls = []

    def make_request(self, method, params):
        self.calls.append(method)
        return self.response


def test_eth_call_falls_back_when_private_circuits_are_open():
    made = []

    def factory(url):
        p = PublicProvider(url, {"jsonrpc": "2.0", "id": 1, "result": "0x01"})
        made.append(p)
        return p

    provider = ReadOnlyPublicFallbackProvider(
        PrivateProvider(error=ConnectionError("all configured RPC provider circuits are open")),
        public_urls=["https://public.example"],
        provider_factory=factory,
    )
    response = provider.make_request("eth_call", [{}, "latest"])
    assert response["result"] == "0x01"
    assert made[0].calls == ["eth_call"]
    status = provider.status()
    assert status["last_source"] == "OFFICIAL_BNB_PUBLIC"
    assert status["live_authority"] is False
    assert status["wallet_authority"] is False
    assert "https://public.example" not in str(status)


def test_eth_getlogs_never_uses_public_fallback():
    made = []

    def factory(url):
        p = PublicProvider(url)
        made.append(p)
        return p

    provider = ReadOnlyPublicFallbackProvider(
        PrivateProvider(error=ConnectionError("private unavailable")),
        public_urls=["https://public.example"],
        provider_factory=factory,
    )
    with pytest.raises(ConnectionError):
        provider.make_request("eth_getLogs", [{}])
    assert made[0].calls == []
    assert provider.status()["eth_getLogs_public_fallback"] is False


def test_transaction_submission_never_uses_public_fallback():
    made = []

    def factory(url):
        p = PublicProvider(url)
        made.append(p)
        return p

    provider = ReadOnlyPublicFallbackProvider(
        PrivateProvider(error=ConnectionError("private unavailable")),
        public_urls=["https://public.example"],
        provider_factory=factory,
    )
    with pytest.raises(ConnectionError):
        provider.make_request("eth_sendRawTransaction", ["0x00"])
    assert made[0].calls == []
    assert provider.status()["transaction_submission_public_fallback"] is False
