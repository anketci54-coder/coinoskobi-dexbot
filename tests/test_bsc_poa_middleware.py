import app.chains.bsc as bsc


class _Onion:
    def __init__(self):
        self.calls = []

    def inject(self, middleware, *, layer):
        self.calls.append((middleware, layer))


class _Client:
    def __init__(self):
        self.middleware_onion = _Onion()


def test_build_bsc_web3_injects_poa_middleware(monkeypatch):
    client = _Client()

    monkeypatch.setattr(
        bsc,
        "ProviderBrokerHTTPProvider",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        bsc,
        "ReadOnlyPublicFallbackProvider",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        bsc,
        "Web3",
        lambda _provider: client,
    )

    result = bsc.build_bsc_web3(
        primary_url="primary",
        secondary_url=None,
        tertiary_url=None,
        quaternary_url=None,
    )

    assert result is client
    assert client.middleware_onion.calls == [
        (bsc.ExtraDataToPOAMiddleware, 0),
    ]
