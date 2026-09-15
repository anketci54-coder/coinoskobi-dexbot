import importlib
import logging


PAIR = "0x" + "11" * 20
TOKEN = "0x" + "22" * 20
QUOTE = "0x" + "33" * 20


class Actor:
    def __init__(self, *, fail=False):
        self.fail = fail

    def status(self):
        if self.fail:
            raise RuntimeError("status unavailable")
        return {
            "accepted_events": 7,
            "unresolved_origins": 9,
            "resolver": {
                "size": 5,
                "provider_calls": 11,
                "resolve_failures": 3,
                "cache_hits": 2,
                "background_scheduled": 12,
                "background_queued": 4,
                "background_drained": 3,
                "background_dropped": 1,
                "pending_background_lookups": 6,
                "deferred_background_lookups": 2,
                "retry_attempts": 3,
                "retry_successes": 1,
                "retry_failures": 2,
            },
        }


class Pipeline:
    def __init__(self, *, actor_fail=False):
        self.native_actor_intelligence = Actor(fail=actor_fail)
        self.pair_membership_verifier = lambda *_: {"state": "VERIFIED"}

    def native_wss_targets(self):
        return [{
            "pair": PAIR,
            "token": TOKEN,
            "quote_token": QUOTE,
            "membership_verified": True,
        }]

    def configure_native_market_flow(self, *_):
        return {"state": "REGISTERED"}

    def confirm_native_market_flow(self, *_):
        return {"state": "VERIFIED"}

    def wait_for_native_market_evidence(self, pairs, *, timeout=10.0):
        return {
            "state": "READY",
            "requested": len(pairs),
            "ready": len(pairs),
            "pending": 0,
        }

    def run_cycle(self, *, pre_analysis_hook=None):
        if pre_analysis_hook:
            pre_analysis_hook([{
                "chain": "bsc",
                "dex": "pancakeswap_v2",
                "pool": PAIR,
                "token": TOKEN,
                "quote_token": QUOTE,
            }])
        return {"state": "RAN"}

    def process_positions(self):
        return []


class Service:
    def __init__(self, _url, pair):
        self.pair = pair

    def bind_callbacks(self, **_kwargs):
        return {"state": "BOUND"}

    def replace_pairs(self, pair):
        self.pair = pair
        return {"state": "UPDATED"}

    def start(self):
        return True

    def stop(self):
        return True

    def status(self):
        return {"state": "READY"}


def _scanner(module, pipeline):
    app = module.build_application(
        pipeline=pipeline,
        wss_service_factory=Service,
    )
    return next(
        job["func"]
        for job in app["runner"].scheduler.jobs
        if job["name"] == "scanner"
    )


def test_scan_logs_live_transaction_origin_status(monkeypatch, caplog):
    module = importlib.import_module("main")
    monkeypatch.setattr(module, "WSS_URL", "wss://provider")
    monkeypatch.setattr(module, "WSS_PAIR", PAIR)
    monkeypatch.setattr(module, "WSS_TOKEN", TOKEN)

    caplog.set_level(logging.INFO)
    assert _scanner(module, Pipeline())() == {"state": "RAN"}

    text = caplog.text
    assert "TX_ORIGIN_STATUS" in text
    assert "accepted=7 unresolved=9" in text
    assert "size=5 provider_calls=11" in text
    assert "resolve_failures=3" in text
    assert "background_dropped=1" in text
    assert "pending=6 deferred=2" in text
    assert "retry_successes=1 retry_failures=2" in text


def test_status_observability_is_fail_soft(monkeypatch, caplog):
    module = importlib.import_module("main")
    monkeypatch.setattr(module, "WSS_URL", "wss://provider")
    monkeypatch.setattr(module, "WSS_PAIR", PAIR)
    monkeypatch.setattr(module, "WSS_TOKEN", TOKEN)

    caplog.set_level(logging.INFO)
    assert _scanner(module, Pipeline(actor_fail=True))() == {"state": "RAN"}
    assert "TX_ORIGIN_STATUS" in caplog.text
    assert "provider_calls=None" in caplog.text
