from app.pipeline.engine import PipelineEngine


class FakeScanner:
    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = 0

    def scan(self):
        self.calls += 1

        if self.error is not None:
            raise self.error

        return list(self.rows)


class FakeCache:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.replaced = []

    def replace(self, row):
        self.replaced.append(dict(row))

    def all(self):
        return list(self.rows)


class EmptyIngress:
    def classify_many(self, rows):
        return {
            "active": [],
            "deferred": [],
            "dropped": [],
            "stats": {
                "input": len(rows),
                "active": 0,
                "deferred": 0,
                "dropped": len(rows),
            },
        }


class FakeManager:
    def __init__(self):
        self.calls = 0

    def process(self):
        self.calls += 1
        return []


def test_scanner_rows_refresh_cache():
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    rows = [{
        "pool": "0xpool",
        "base_token": "bsc_0xtoken",
        "quote_token": "bsc_0xquote",
    }]

    engine.scanner = FakeScanner(rows)
    engine.cache = FakeCache()

    result = engine.refresh_candidate_cache()

    assert result == {
        "state": "REFRESHED",
        "rows": 1,
        "error": None,
    }
    assert engine.scanner.calls == 1
    assert engine.cache.replaced == rows


def test_scanner_failure_uses_existing_cache():
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    engine.scanner = FakeScanner(
        error=RuntimeError("provider down")
    )
    engine.cache = FakeCache([])
    engine.ingress_gate = EmptyIngress()
    engine.manager = FakeManager()

    engine.run_cycle()

    assert engine.last_scanner_refresh[
        "state"
    ] == "FAILED_USING_CACHE"

    assert "RuntimeError" in (
        engine.last_scanner_refresh["error"]
    )

    assert engine.manager.calls == 1


def test_native_wss_targets_observe_all_v2_and_are_bounded(monkeypatch):
    engine = PipelineEngine(
        pair_membership_verifier=lambda *args: {
            "state": "VERIFIED",
        }
    )

    rows = [
        {
            "token": f"0x{i:040x}",
            "quote_token": "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
            "pool": f"0x{i + 100:040x}",
            "dex": "pancakeswap_v2",
            "liquidity": 50000,
            "volume_24h": 25000,
            "buys_24h": 50 + i,
            "fdv": 100000,
        }
        for i in range(1, 5)
    ]

    # Observation must not depend on ingress admission.
    engine.ingress_gate = None

    monkeypatch.setattr(engine.cache, "all", lambda: rows)

    targets = engine.native_wss_targets(max_pairs=3)

    assert len(targets) == 3
    assert len({row["pair"] for row in targets}) == 3
    assert all(row["token"] for row in targets)
    assert all(row["quote_token"] for row in targets)
