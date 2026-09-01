from app.pipeline.engine import (
    PipelineEngine,
    _runtime_observation_watch_snapshot,
    _runtime_should_watch_movement,
    _runtime_watch_candidate,
)


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

    # This test owns the Gecko-cache fallback contract.
    # Durable host UniverseRegistry contents must not affect it.
    monkeypatch.setattr(
        engine.hot_deep_path,
        "native_wss_targets",
        lambda *, limit: [],
    )
    monkeypatch.setattr(
        engine.universe_registry,
        "count",
        lambda: 0,
    )

    targets = engine.native_wss_targets(max_pairs=3)

    assert len(targets) == 3
    assert len({row["pair"] for row in targets}) == 3
    assert all(row["token"] for row in targets)
    assert all(row["quote_token"] for row in targets)


def test_movement_only_candidate_is_retained_for_real_price_refresh():
    class ObservationScanner:
        def __init__(self):
            self.price_calls = []

        def scan(self):
            return [{
                "pool": "0xcurrentpool",
                "base_token": "bsc_0xcurrent",
                "quote_token": "bsc_0xquote",
            }]

        def pool_prices(self, pools):
            self.price_calls.append(
                list(pools)
            )

            return {
                "0xwatchpool": 1.25,
            }

    class ObservationCache:
        def __init__(self):
            self.replaced = []
            self.updated = []
            self.pruned = []

        def replace(self, row):
            self.replaced.append(
                dict(row)
            )

        def update_pool_price(
            self,
            pool,
            price,
        ):
            self.updated.append(
                (pool, price)
            )

            return 1

        def prune_except(
            self,
            pools,
            preserve_tokens=None,
        ):
            self.pruned.append({
                "pools": list(pools),
                "preserve_tokens": list(
                    preserve_tokens or []
                ),
            })

            return 0

    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    engine.scanner = ObservationScanner()
    engine.cache = ObservationCache()

    _runtime_watch_candidate(
        "0xwatch",
        "0xwatchpool",
        enabled=True,
    )

    try:
        result = (
            engine.refresh_candidate_cache()
        )

        snapshot = (
            _runtime_observation_watch_snapshot()
        )

        assert result == {
            "state": "REFRESHED",
            "rows": 1,
            "error": None,
        }

        assert snapshot == {
            "0xwatch": "0xwatchpool",
        }

        assert (
            engine.scanner.price_calls
            == [["0xwatchpool"]]
        )

        assert engine.cache.updated == [
            ("0xwatchpool", 1.25)
        ]

        assert len(engine.cache.pruned) == 1

        assert "0xwatch" in (
            engine.cache.pruned[0][
                "preserve_tokens"
            ]
        )

    finally:
        _runtime_watch_candidate(
            "0xwatch",
            "0xwatchpool",
            enabled=False,
        )



def test_movement_watch_allows_other_blockers_to_remain():
    assert (
        _runtime_should_watch_movement(
            "PLAN_BLOCKED",
            [
                "EMPIRICAL_MOVEMENT_INSUFFICIENT",
                "LP_PROTECTION_UNKNOWN",
                "RETURN_RISK_UNOBSERVABLE",
                "MATHEMATICAL_POSITION_SIZE_ZERO",
            ],
        )
        is True
    )

    assert (
        _runtime_should_watch_movement(
            "PLAN_BLOCKED",
            [
                "LP_PROTECTION_UNKNOWN",
                "MATHEMATICAL_POSITION_SIZE_ZERO",
            ],
        )
        is False
    )

    assert (
        _runtime_should_watch_movement(
            None,
            [
                "EMPIRICAL_MOVEMENT_INSUFFICIENT",
            ],
        )
        is False
    )



def test_durable_counterfactual_prices_use_scan_then_bounded_fetch():
    class DurableScanner:
        def __init__(self):
            self.price_calls = []

        def scan(self):
            return [{
                "pool": "0xcurrentpool",
                "base_token": "bsc_0xcurrent",
                "quote_token": "bsc_0xquote",
                "price_usd": 1.25,
            }]

        def pool_prices(self, pools):
            pools = list(pools)

            assert len(pools) <= 30

            self.price_calls.append(
                pools
            )

            return {
                pool: 2.0
                for pool in pools
            }

    class DurableCache:
        def __init__(self):
            self.replaced = []

        def replace(self, row):
            self.replaced.append(
                dict(row)
            )

    class DurableStore:
        def __init__(self):
            self.observed = []

        def pending_pool_snapshot(
            self,
            max_entries=120,
        ):
            assert max_entries == 120

            result = {
                "0xdirect": "0xcurrentpool",
            }

            for index in range(31):
                result[f"0xfetch{index}"] = (
                    f"0xpool{index:02d}"
                )

            return result

        def observe_durable(
            self,
            *,
            token,
            current_price,
        ):
            self.observed.append(
                (token, current_price)
            )

            return {
                "state": "OBSERVED",
            }

    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    engine.scanner = DurableScanner()
    engine.cache = DurableCache()
    engine.counterfactual_store = (
        DurableStore()
    )

    result = engine.refresh_candidate_cache()

    stats = (
        engine.last_counterfactual_refresh
    )

    assert result == {
        "state": "REFRESHED",
        "rows": 1,
        "error": None,
    }

    assert stats["state"] == "READY"
    assert stats["pending"] == 32
    assert stats["observed"] == 32
    assert stats["direct"] == 1
    assert stats["fetched"] == 31
    assert stats["failed"] == 0
    assert stats["requests"] == 2

    assert engine.scanner.price_calls == [
        [
            f"0xpool{index:02d}"
            for index in range(30)
        ],
        ["0xpool30"],
    ]

    assert (
        "0xdirect",
        1.25,
    ) in engine.counterfactual_store.observed

    assert (
        "0xfetch30",
        2.0,
    ) in engine.counterfactual_store.observed

    assert stats["decision_authority"] is False
    assert stats["paper_authority"] is False
    assert stats["live_authority"] is False
    assert stats["wallet_authority"] is False
    assert stats["execution_authority"] is False
