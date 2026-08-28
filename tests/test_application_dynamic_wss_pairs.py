import importlib


PAIR1 = "0x" + "11" * 20
PAIR2 = "0x" + "22" * 20
PAIR3 = "0x" + "33" * 20
PAIR4 = "0x" + "44" * 20
TOKEN = "0x" + "55" * 20
QUOTE = "0x" + "66" * 20


class Pipeline:
    def __init__(self):
        self.calls = 0
        self.configured = []
        self.sequence = []
        self.pair_membership_verifier = (
            lambda pair, token, quote: {
                "state": "VERIFIED"
            }
        )

    def native_wss_targets(self):
        self.sequence.append("targets")
        self.calls += 1
        if self.calls == 1:
            pairs = [PAIR1]
        else:
            return [
                {
                    "pair": PAIR2,
                    "token": TOKEN,
                    "quote_token": QUOTE,
                    "membership_verified": True,
                    "selection_reason": "UNIVERSE_BOOTSTRAP",
                }
            ]
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
        self.sequence.append("configure")
        self.configured.append(pair)
        return {"state": "REGISTERED"}

    def confirm_native_market_flow(self, pair, token, quote):
        self.sequence.append("confirm")
        return {"state": "VERIFIED"}

    def wait_for_native_market_evidence(
        self,
        pairs,
        *,
        timeout=10.0,
    ):
        self.sequence.append("wait")
        self.waited_pairs = list(pairs)
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

    def run_cycle(
        self,
        *,
        pre_analysis_hook=None,
    ):
        self.sequence.append("refresh")

        if pre_analysis_hook is not None:
            pre_analysis_hook([
                {
                    "chain": "bsc",
                    "dex": "pancakeswap_v2",
                    "pool": PAIR3,
                    "token": TOKEN,
                    "quote_token": QUOTE,
                },
                {
                    "chain": "bsc",
                    "dex": "pancakeswap_v3",
                    "pool": PAIR4,
                    "token": TOKEN,
                    "quote_token": QUOTE,
                },
            ])

        self.sequence.append("analyze")

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


def test_scanner_refresh_prioritizes_verified_v2_candidate_wss_pair(monkeypatch):
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

    pipeline.sequence.clear()

    assert scanner["func"]() == {"state": "RAN"}

    assert pipeline.sequence[0] == "refresh"
    assert pipeline.sequence[-1] == "analyze"

    assert (
        pipeline.sequence.index("targets")
        < pipeline.sequence.index("analyze")
    )

    assert (
        pipeline.sequence.index("confirm")
        < pipeline.sequence.index("wait")
        < pipeline.sequence.index("analyze")
    )

    assert app["services"][0].pair == [PAIR3, PAIR2]
    assert app["services"][0].replacements == [[PAIR3, PAIR2]]
    assert pipeline.waited_pairs == [PAIR3]
    assert PAIR4 not in pipeline.configured


def test_candidate_wss_targets_are_bounded(monkeypatch):
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

    rows = [
        {
            "chain": "bsc",
            "dex": "pancakeswap_v2",
            "pool": "0x" + f"{index:040x}",
            "token": TOKEN,
            "quote_token": QUOTE,
        }
        for index in range(1, 40)
    ]

    original_run_cycle = pipeline.run_cycle

    def run_cycle(*, pre_analysis_hook=None):
        if pre_analysis_hook is not None:
            pre_analysis_hook(rows)
        return {"state": "RAN"}

    pipeline.run_cycle = run_cycle
    try:
        assert scanner["func"]() == {"state": "RAN"}
    finally:
        pipeline.run_cycle = original_run_cycle

    candidate_pairs = [
        pair
        for pair in pipeline.configured
        if pair not in {PAIR1, PAIR2}
    ]
    assert len(set(candidate_pairs)) == module.SCAN_NATIVE_WSS_LIMIT
