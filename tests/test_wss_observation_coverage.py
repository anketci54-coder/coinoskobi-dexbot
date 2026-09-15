import importlib


TOKEN = "0x" + "55" * 20
QUOTE = "0x" + "66" * 20
BOOT_PAIR = "0x" + "77" * 20


class Pipeline:
    def __init__(self):
        self.configured = []
        self.pair_membership_verifier = (
            lambda *_: {"state": "VERIFIED"}
        )

    def native_wss_targets(self):
        return []

    def configure_native_market_flow(self, pair, token, quote):
        self.configured.append(pair)
        return {"state": "REGISTERED"}

    def confirm_native_market_flow(self, pair, token, quote):
        return {"state": "VERIFIED"}

    def wait_for_native_market_evidence(self, pairs, *, timeout=10.0):
        return {
            "state": "READY",
            "requested": len(pairs),
            "ready": len(pairs),
            "pending": 0,
        }

    async def on_native_event(self, event):
        return True

    async def on_native_retraction(self, event):
        return True

    def run_cycle(self, *, pre_analysis_hook=None):
        rows = [
            {
                "chain": "bsc",
                "dex": "pancakeswap_v2",
                "pool": "0x" + f"{index:040x}",
                "token": TOKEN,
                "quote_token": QUOTE,
            }
            for index in range(1, 301)
        ]
        if pre_analysis_hook is not None:
            pre_analysis_hook(rows)
        return {"state": "RAN"}

    def process_positions(self):
        return []


class Service:
    def __init__(self, url, pair):
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


def test_scanner_wss_uses_full_existing_global_capacity(monkeypatch):
    module = importlib.import_module("main")

    assert module.SCAN_NATIVE_WSS_LIMIT == 256
    assert module.SCAN_NATIVE_WSS_RETENTION_LIMIT == 256

    monkeypatch.setattr(module, "WSS_URL", "wss://provider")
    monkeypatch.setattr(module, "WSS_PAIR", BOOT_PAIR)
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

    bound = app["services"][0].pair
    assert isinstance(bound, list)
    assert len(bound) == 256
    assert len(set(bound)) == 256
    assert BOOT_PAIR not in bound
