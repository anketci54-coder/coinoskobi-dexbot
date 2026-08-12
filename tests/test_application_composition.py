import importlib


class FakePipeline:
    def run_cycle(self):
        return None


class FakeWSSService:
    def __init__(
        self,
        url,
        pair,
    ):
        self.url = url
        self.pair = pair

    def start(self):
        return True

    def stop(self):
        return True

    def status(self):
        return {
            "state": "READY",
            "application_owned": True,
        }


def test_application_without_wss_config(
    monkeypatch,
):
    module = importlib.import_module(
        "main"
    )

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "",
    )

    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        "",
    )

    app = module.build_application(
        pipeline=FakePipeline(),
        wss_service_factory=(
            FakeWSSService
        ),
    )

    assert app[
        "wss_configured"
    ] is False

    assert app[
        "services"
    ] == []


def test_application_owns_wss_when_configured(
    monkeypatch,
):
    module = importlib.import_module(
        "main"
    )

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "wss://provider",
    )

    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        "0xpair",
    )

    app = module.build_application(
        pipeline=FakePipeline(),
        wss_service_factory=(
            FakeWSSService
        ),
    )

    assert app[
        "wss_configured"
    ] is True

    assert len(
        app["services"]
    ) == 1

    service = app[
        "services"
    ][0]

    assert service.url == (
        "wss://provider"
    )

    assert service.pair == (
        "0xpair"
    )

    assert (
        app["runner"].services[
            0
        ]
        is service
    )


def test_application_composition_authority_zero(
    monkeypatch,
):
    module = importlib.import_module(
        "main"
    )

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "",
    )

    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        "",
    )

    app = module.build_application(
        pipeline=FakePipeline(),
    )

    assert app[
        "decision_authority"
    ] is False

    assert app[
        "live_authority"
    ] is False

    assert app[
        "execution_authority"
    ] is False
