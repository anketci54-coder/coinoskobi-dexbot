import importlib


PAIR1 = "0x" + "11" * 20
PAIR2 = "0x" + "22" * 20
PAIR3 = "0x" + "33" * 20
TOKEN = "0x" + "44" * 20
QUOTE = "0x" + "55" * 20


class Pipeline:
    def __init__(self):
        self.calls = 0
        self.configured = []

    def native_wss_targets(self):
        self.calls += 1
        pairs = [PAIR1] if self.calls == 1 else [PAIR2, PAIR3]
        return [
            {
                "pair": pair,
                "token": TOKEN,
                "quote_token": QUOTE,
                "membership_verified": True,
            }
            for pair in pairs
        ]

    def configure_native_market_flow(self, pair, token, quote):
        self.configured.append(pair)
        return {"state": "REGISTERED"}

    def confirm_native_market_flow(self, pair, token, quote):
        return {"state": "VERIFIED"}

    async def on_native_event(self, event):
        return True

    async def on_native_retraction(self, event):
        return True

    def run_cycle(self):
        return {"state": "RAN"}

    def process_positions(self):
        return []


class Service:
    def __init__(self, url, pair):
        self.url = url
        self.pair = pair
        self.replacements = []

    def bind_callbacks(self, **kwargs):
        return {"state": "BOUND"}

    def replace_pairs(self, pair):
        self.pair = pair
        self.replacements.append(pair)
        return {"state": "UPDATED"}

    def start(self):
        return True

    def stop(self):
        return True

    def status(self):
        return {"state": "NOT_STARTED"}


def test_scanner_refresh_rebinds_verified_wss_pairs(monkeypatch):
    module = importlib.import_module("main")

    monkeypatch.setattr(module, "WSS_URL", "wss://provider")
    monkeypatch.setattr(module, "WSS_PAIR", PAIR1)
    monkeypatch.setattr(module, "WSS_TOKEN", TOKEN)

    pipeline = Pipeline()
    app = module.build_application(
        pipeline=pipeline,
        wss_service_factory=Service,
    )

    scanner = next(
        job for job in app["runner"].scheduler.jobs
        if job["name"] == "scanner"
    )

    assert scanner["func"]() == {"state": "RAN"}
    assert app["services"][0].pair == [PAIR2, PAIR3]
    assert app["services"][0].replacements == [[PAIR2, PAIR3]]
