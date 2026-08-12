import importlib


class FakePipeline:
    def __init__(self):
        self.registration = None
        self.events = []
        self.retractions = []

    def run_cycle(self):
        return None

    def configure_native_market_flow(
        self,
        pair,
        token,
        quote,
    ):
        self.registration = (
            pair,
            token,
            quote,
        )

        return {
            "state": "REGISTERED"
        }

    async def on_native_event(
        self,
        event,
    ):
        self.events.append(event)
        return True

    async def on_native_retraction(
        self,
        event,
    ):
        self.retractions.append(
            event
        )
        return True


class FakeService:
    def __init__(
        self,
        url,
        pair,
    ):
        self.url = url
        self.pair = pair
        self.on_event = None
        self.on_retraction = None

    def bind_callbacks(
        self,
        *,
        on_event=None,
        on_retraction=None,
    ):
        self.on_event = on_event
        self.on_retraction = (
            on_retraction
        )

        return {
            "state": "BOUND"
        }

    def start(self):
        return True

    def stop(self):
        return True

    def status(self):
        return {
            "state": "READY"
        }


def test_application_binds_real_market_flow(
    monkeypatch,
):
    module = importlib.import_module(
        "main"
    )

    pair = (
        "0x00000000000000000000000000000000000000aa"
    )

    token = (
        "0x0000000000000000000000000000000000000001"
    )

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "wss://provider",
    )

    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        pair,
    )

    monkeypatch.setattr(
        module,
        "WSS_TOKEN",
        token,
    )

    pipeline = FakePipeline()

    app = module.build_application(
        pipeline=pipeline,
        wss_service_factory=(
            FakeService
        ),
    )

    assert app[
        "market_flow_bound"
    ] is True

    assert (
        pipeline.registration
        is not None
    )

    service = app[
        "services"
    ][0]

    assert (
        service.on_event
        == pipeline.on_native_event
    )

    assert (
        service.on_retraction
        == pipeline.on_native_retraction
    )


def test_missing_target_token_never_guesses(
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

    monkeypatch.setattr(
        module,
        "WSS_TOKEN",
        "",
    )

    pipeline = FakePipeline()

    app = module.build_application(
        pipeline=pipeline,
        wss_service_factory=(
            FakeService
        ),
    )

    assert app[
        "wss_configured"
    ] is True

    assert app[
        "market_flow_bound"
    ] is False

    assert (
        pipeline.registration
        is None
    )
