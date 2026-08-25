import importlib

from app.dex.native_ingestion import SYNC_TOPIC
from app.dex.open_position_hot_path import (
    HotPositionWSSBridge,
    merge_wss_targets,
    open_position_targets,
    process_hot_positions,
)


OPEN_PAIR = "0x" + "11" * 20
SCAN_PAIR1 = "0x" + "22" * 20
SCAN_PAIR2 = "0x" + "33" * 20
TOKEN = "0x" + "01" * 20
TOKEN2 = "0x" + "02" * 20
QUOTE = "0x" + "ff" * 20


def word(value):
    return f"{value:064x}"


def sync_event(
    reserve0,
    reserve1,
    *,
    pair=OPEN_PAIR,
):
    return {
        "state": "NORMALIZED",
        "event_type": "SYNC",
        "address": pair,
        "topics": [SYNC_TOPIC],
        "data": (
            "0x"
            + word(reserve0)
            + word(reserve1)
        ),
    }


class FakeDB:
    def __init__(self, positions=None):
        self.positions = list(
            positions or []
        )

    def open_positions(self):
        return [
            dict(row)
            for row in self.positions
        ]


class FakeCache:
    def __init__(self, rows):
        self.rows = [
            dict(row)
            for row in rows
        ]
        self.update_calls = []

    def all(self):
        return [
            dict(row)
            for row in self.rows
        ]

    def pool_for_token(self, token):
        wanted = str(token).lower()

        for row in self.rows:
            cached = str(
                row.get("token")
                or ""
            ).lower()

            if cached.startswith("bsc_"):
                cached = cached[4:]

            if cached == wanted:
                return row.get("pool")

        return None

    def update_pool_price(self, pool, price):
        self.update_calls.append(
            (pool, price)
        )

        for row in self.rows:
            if str(
                row.get("pool")
            ).lower() == str(pool).lower():
                row["price_usd"] = float(
                    price
                )
                return 1

        return 0


class Manager:
    def __init__(
        self,
        db,
        price=None,
    ):
        self.db = db
        self.price = price
        self.hybrid_exit_evidence = None

    def process(self):
        return [
            self.price.get_price(TOKEN)
        ]


class Pipeline:
    def __init__(
        self,
        positions,
        rows,
    ):
        self.cache = FakeCache(rows)
        self.manager = Manager(
            FakeDB(positions)
        )
        self.pair_membership_verifier = (
            lambda *_: {
                "state": "VERIFIED",
            }
        )

    def _hybrid_exit_runtime_evidence(
        self,
        position,
    ):
        return {
            "state": "READY",
        }


class FallbackPrice:
    def get_price(self, token):
        return 99.0


def position():
    return {
        "id": 1,
        "status": "OPEN",
        "trade_policy": "VUR_KAC",
        "token": TOKEN,
        "pool": OPEN_PAIR,
        "dex": "pancakeswap_v2",
        "opening_context_json": "{}",
    }


def cache_row(
    pair=OPEN_PAIR,
    token=TOKEN,
    price=10.0,
):
    return {
        "pool": pair,
        "token": f"bsc_{token}",
        "quote_token": f"bsc_{QUOTE}",
        "dex": "pancakeswap_v2",
        "price_usd": price,
    }


def scanner_target(pair, token):
    return {
        "pair": pair,
        "token": token,
        "quote_token": QUOTE,
        "membership_verified": True,
    }


def test_open_position_targets_are_verified_and_prioritized():
    pipeline = Pipeline(
        [position()],
        [cache_row()],
    )

    open_targets = open_position_targets(
        pipeline
    )

    assert len(open_targets) == 1
    assert open_targets[0]["pair"] == OPEN_PAIR
    assert open_targets[0]["target_source"] == "OPEN_POSITION"

    merged = merge_wss_targets(
        pipeline,
        [
            scanner_target(
                SCAN_PAIR1,
                TOKEN2,
            ),
            scanner_target(
                SCAN_PAIR2,
                "0x" + "03" * 20,
            ),
        ],
        max_pairs=2,
    )

    assert merged["address_count"] == 2
    assert merged["open_target_count"] == 1
    assert merged["targets"][0]["pair"] == OPEN_PAIR
    assert merged["targets"][0]["hot_open_position"] is True
    assert merged["targets"][1]["pair"] == SCAN_PAIR1


def test_sync_hot_price_is_anchored_then_updates_exact_pool():
    pipeline = Pipeline(
        [position()],
        [cache_row(price=10.0)],
    )

    bridge = HotPositionWSSBridge()

    bridge.replace_targets(
        [
            scanner_target(
                OPEN_PAIR,
                TOKEN,
            )
        ],
        open_pairs=[OPEN_PAIR],
    )

    first = bridge.observe_event(
        sync_event(
            100,
            200,
        )
    )

    assert first["state"] == "BASELINED"
    assert pipeline.cache.update_calls == []

    anchored = bridge.drain_price_updates(
        pipeline
    )

    assert anchored["state"] == "ANCHORED"
    assert anchored["updated"] == 0
    assert pipeline.cache.rows[0]["price_usd"] == 10.0

    queued = bridge.observe_event(
        sync_event(
            100,
            150,
        )
    )

    assert queued["state"] == "HOT_PRICE_QUEUED"
    assert pipeline.cache.update_calls == []

    updated = bridge.drain_price_updates(
        pipeline
    )

    assert updated["state"] == "UPDATED"
    assert updated["updated"] == 1
    assert abs(
        pipeline.cache.rows[0]["price_usd"]
        - 7.5
    ) < 1e-12

    status = bridge.status()
    assert status["sqlite_from_wss_thread"] is False
    assert status["pending_count"] == 0


def test_provider_anchor_rebases_future_relative_price():
    pipeline = Pipeline(
        [position()],
        [cache_row(price=10.0)],
    )

    bridge = HotPositionWSSBridge()
    bridge.replace_targets(
        [scanner_target(OPEN_PAIR, TOKEN)],
        open_pairs=[OPEN_PAIR],
    )

    bridge.observe_event(
        sync_event(100, 200)
    )
    bridge.drain_price_updates(
        pipeline
    )

    pipeline.cache.update_pool_price(
        OPEN_PAIR,
        12.0,
    )

    anchor = bridge.anchor_from_cache(
        pipeline
    )

    assert anchor["state"] == "ANCHORED"

    bridge.observe_event(
        sync_event(100, 100)
    )
    bridge.drain_price_updates(
        pipeline
    )

    assert abs(
        pipeline.cache.rows[0]["price_usd"]
        - 6.0
    ) < 1e-12


def test_retraction_invalidates_hot_price_anchor():
    pipeline = Pipeline(
        [position()],
        [cache_row(price=10.0)],
    )

    bridge = HotPositionWSSBridge()
    bridge.replace_targets(
        [scanner_target(OPEN_PAIR, TOKEN)],
        open_pairs=[OPEN_PAIR],
    )

    bridge.observe_event(
        sync_event(100, 200)
    )
    bridge.drain_price_updates(
        pipeline
    )

    reset = bridge.observe_retraction({
        "address": OPEN_PAIR,
    })

    assert reset["state"] == "RESET"

    bridge.observe_event(
        sync_event(100, 100)
    )

    anchored = bridge.drain_price_updates(
        pipeline
    )

    assert anchored["state"] == "ANCHORED"
    assert pipeline.cache.rows[0]["price_usd"] == 10.0


def test_hot_manager_uses_exact_open_pool_price_not_token_latest_fallback():
    pipeline = Pipeline(
        [position()],
        [
            cache_row(
                pair=OPEN_PAIR,
                token=TOKEN,
                price=7.5,
            ),
            cache_row(
                pair=SCAN_PAIR1,
                token=TOKEN,
                price=50.0,
            ),
        ],
    )

    pipeline.manager.price = FallbackPrice()

    result = process_hot_positions(
        pipeline
    )

    assert result == [7.5]
    assert isinstance(
        pipeline.manager.price,
        FallbackPrice,
    )


def test_application_adds_one_second_hot_job_only_for_capable_runtime(
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
        SCAN_PAIR1,
    )
    monkeypatch.setattr(
        module,
        "WSS_TOKEN",
        TOKEN2,
    )

    class RuntimePipeline(Pipeline):
        def __init__(self):
            super().__init__(
                [position()],
                [cache_row()],
            )
            self.configured = []

        def refresh_candidate_cache(self):
            return {
                "state": "READY",
            }

        def native_wss_targets(self):
            return [
                scanner_target(
                    SCAN_PAIR1,
                    TOKEN2,
                )
            ]

        def configure_native_market_flow(
            self,
            pair,
            token,
            quote,
        ):
            self.configured.append(pair)
            return {
                "state": "REGISTERED",
            }

        def confirm_native_market_flow(
            self,
            pair,
            token,
            quote,
        ):
            return {
                "state": "VERIFIED",
            }

        async def on_native_event(
            self,
            event,
        ):
            return True

        async def on_native_retraction(
            self,
            event,
        ):
            return True

        def wait_for_native_market_evidence(
            self,
            pairs,
            *,
            timeout=10.0,
        ):
            return {
                "state": "READY",
                "requested": len(pairs),
                "ready": len(pairs),
                "pending": 0,
            }

        def run_cycle(
            self,
            *,
            pre_analysis_hook=None,
        ):
            return {
                "state": "READY",
            }

        def refresh_open_position_prices(
            self,
        ):
            return {
                "state": "REFRESHED",
                "open_positions": 1,
                "refreshed": 1,
                "failed": 0,
            }

        def process_positions(self):
            return []

    class Service:
        def __init__(self, url, pair):
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
            self.on_retraction = on_retraction
            return {
                "state": "BOUND",
            }

        def replace_pairs(self, pair):
            self.pair = pair
            return {
                "state": "UPDATED",
            }

        def start(self):
            return True

        def stop(self):
            return True

        def status(self):
            return {
                "state": "READY",
            }

    pipeline = RuntimePipeline()

    app = module.build_application(
        pipeline=pipeline,
        wss_service_factory=Service,
    )

    jobs = {
        job["name"]: job
        for job in app[
            "runner"
        ].scheduler.jobs
    }

    assert app["hot_position_bound"] is True
    assert "paper_hot_manager" in jobs
    assert jobs[
        "paper_hot_manager"
    ]["interval"] == 1

    initial_pairs = app[
        "services"
    ][0].pair

    assert isinstance(
        initial_pairs,
        list,
    )
    assert initial_pairs[0] == OPEN_PAIR
    assert SCAN_PAIR1 in initial_pairs
