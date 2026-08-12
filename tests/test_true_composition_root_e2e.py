import asyncio
import importlib

from app.dex.native_ingestion import SWAP_TOPIC
from app.dex.transaction_origin import TransactionOriginResolver
from app.paper.manager import PaperManager


PAIR = "0x00000000000000000000000000000000000000aa"
TOKEN = "0x0000000000000000000000000000000000000001"
WALLET = "0x0000000000000000000000000000000000000123"


def word(value):
    return f"{value:064x}"


class FakeService:
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
        return {"state": "BOUND"}

    def start(self):
        return True

    def stop(self):
        return True

    def status(self):
        return {"state": "READY"}


class FakeDB:
    def __init__(self):
        self.closed = []

    def open_positions(self):
        return [{
            "id": 1,
            "token": TOKEN,
            "created_at": "2026-01-01T00:00:00+00:00",
            "closed_at": "",
            "highest_price": 1.0,
            "lowest_price": 1.0,
            "entry_price": 1.0,
            "token_amount": 1.0,
            "amount_bnb": 1.0,
            "swap_fee": 0.0,
            "buy_tax": 0.0,
            "sell_tax": 0.0,
            "slippage": 0.0,
            "mev": 0.0,
            "gas_buy": 0.0,
            "gas_sell": 0.0,
        }]

    def update_position(self, position_id, data):
        return True

    def close_position(self, position_id, data):
        self.closed.append((position_id, dict(data)))
        return True


class FakePrice:
    def get_price(self, token):
        return 1.30


def test_true_composition_root_e2e(monkeypatch):
    module = importlib.import_module("main")

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "wss://provider",
    )
    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        PAIR,
    )
    monkeypatch.setattr(
        module,
        "WSS_TOKEN",
        TOKEN,
    )

    app = module.build_application(
        wss_service_factory=FakeService,
    )

    pipeline = app["pipeline"]
    service = app["services"][0]

    assert app["wss_configured"] is True
    assert app["market_flow_bound"] is True
    assert app["paper_lifecycle_bound"] is True

    # deterministic real tx.from resolver
    pipeline.native_actor_intelligence.resolver = (
        TransactionOriginResolver(
            fetcher=lambda _: {
                "from": WALLET
            }
        )
    )

    # inject one real normalized Swap event through
    # the actual composition-root callback wiring
    event = {
        "state": "NORMALIZED",
        "event_type": "SWAP",
        "event_identity": "0xaaa:0x1",
        "transaction_hash": "0xaaa",
        "log_index": "0x1",
        "block_number": "0x10",
        "removed": False,
        "address": PAIR,
        "topics": [
            SWAP_TOPIC,
        ],
        "data": (
            "0x"
            + word(0)
            + word(10)
            + word(5)
            + word(0)
        ),
    }

    asyncio.run(
        service.on_event(event)
    )

    actor = (
        pipeline.native_actor_intelligence
        .snapshot(PAIR)
    )

    assert actor["state"] == "READY"
    assert actor["wallet_id"] == f"bsc:{WALLET}"

    market = (
        pipeline.native_market_flow
        .snapshot(
            PAIR,
            candidate={
                "pool": PAIR,
                "token": TOKEN,
                "liquidity": 100000,
                "volume_24h": 250000,
                "price_usd": 1.0,
            },
        )
    )

    assert market["state"] == "READY"
    assert (
        market["flow_intelligence"]["buy_flow"]
        == 1
    )

    # existing readmodels must now contain the real actor
    intelligence = pipeline.intelligence.build(
        TOKEN,
        market_input=(
            market["market_intelligence"]
        ),
        flow_input=(
            market["flow_intelligence"]
        ),
        wallet_id=f"bsc:{WALLET}",
        adversary_key=f"bsc:{WALLET}",
    )

    assert (
        intelligence["wallet_readmodel"]["state"]
        == "READY"
    )
    assert (
        intelligence["adversary_readmodel"]["state"]
        == "READY"
    )

    # real paper close -> existing Phase 11 feed
    manager = PaperManager(
        learning_feed=(
            pipeline.learning_outcome_feed
        )
    )
    manager.db = FakeDB()
    manager.price = FakePrice()

    result = manager.process()

    assert result[0]["data"]["action"] == "CLOSE"
    assert (
        result[0]["data"]["learning"]["state"]
        == "OBSERVED"
    )

    learning = (
        pipeline.learning_outcome_feed
        .calibration_snapshot()
    )

    assert learning["state"] == "READY"
    assert (
        learning["payload"]["proposal_only"]
        is True
    )
    assert (
        learning["payload"][
            "automatic_apply_allowed"
        ]
        is False
    )

    # final authority boundary
    assert (
        intelligence["execution_authority"]
        is False
    )
    assert (
        pipeline.learning_outcome_feed
        .status()["execution_authority"]
        is False
    )


def test_true_runner_lifecycle_e2e(monkeypatch):
    module = importlib.import_module("main")

    monkeypatch.setattr(module, "WSS_URL", "wss://provider")
    monkeypatch.setattr(module, "WSS_PAIR", PAIR)
    monkeypatch.setattr(module, "WSS_TOKEN", TOKEN)

    lifecycle = []

    class RunnerService(FakeService):
        def start(self):
            lifecycle.append("SERVICE_START")
            return True

        def stop(self):
            lifecycle.append("SERVICE_STOP")
            return True

    class RunnerPipeline:
        def __init__(self):
            self.scan_count = 0
            self.position_count = 0

        def configure_native_market_flow(
            self,
            pair,
            token,
            wrapped_native,
        ):
            lifecycle.append("MARKET_FLOW_CONFIGURED")
            return {"state": "REGISTERED"}

        async def on_native_event(self, event):
            return {"state": "ACCEPTED"}

        async def on_native_retraction(self, event):
            return {"state": "RETRACTED"}

        def run_cycle(self):
            self.scan_count += 1
            lifecycle.append("SCAN")

        def process_positions(self):
            self.position_count += 1
            lifecycle.append("PAPER_MANAGER")

    pipeline = RunnerPipeline()

    app = module.build_application(
        pipeline=pipeline,
        wss_service_factory=RunnerService,
    )

    runner = app["runner"]

    # Scheduler jobs are due immediately on first tick.
    # Stop after that first complete runner iteration.
    def stop_after_first_tick(_):
        runner.stop()

    runner.sleep_func = stop_after_first_tick

    runner.run()

    assert app["wss_configured"] is True
    assert app["market_flow_bound"] is True
    assert app["paper_lifecycle_bound"] is True

    assert pipeline.scan_count == 1
    assert pipeline.position_count == 1

    assert lifecycle.count("SERVICE_START") == 1
    assert lifecycle.count("SERVICE_STOP") == 1

    assert lifecycle.index("SERVICE_START") < lifecycle.index("SCAN")
    assert lifecycle.index("SERVICE_START") < lifecycle.index("PAPER_MANAGER")
    assert lifecycle.index("SERVICE_STOP") > lifecycle.index("SCAN")
    assert lifecycle.index("SERVICE_STOP") > lifecycle.index("PAPER_MANAGER")

    assert runner.running is False
    assert runner.services_started is False
    assert runner.last_service_error is None

    assert app["decision_authority"] is False
    assert app["live_authority"] is False
    assert app["execution_authority"] is False


def test_runner_owned_composition_root_lifecycle(monkeypatch):
    module = importlib.import_module("main")

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "wss://provider",
    )
    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        PAIR,
    )
    monkeypatch.setattr(
        module,
        "WSS_TOKEN",
        TOKEN,
    )

    class LifecycleService(FakeService):
        def __init__(self, url, pair):
            super().__init__(url, pair)
            self.started = 0
            self.stopped = 0

        def start(self):
            self.started += 1
            return True

        def stop(self):
            self.stopped += 1
            return True

    app = module.build_application(
        wss_service_factory=LifecycleService,
    )

    runner = app["runner"]
    pipeline = app["pipeline"]
    service = app["services"][0]

    # Real composition-root ownership:
    # Runner owns the same service and same pipeline jobs.
    assert runner.services == [service]

    scheduled_names = {
        task["name"]
        for task in runner.scheduler.jobs
    }

    assert "scanner" in scheduled_names
    assert "paper_manager" in scheduled_names

    # Runner service lifecycle, not manual direct service ownership.
    runner._start_services()

    assert runner.services_started is True
    assert service.started == 1

    # Callback wiring belongs to the production pipeline instance.
    assert service.on_event.__self__ is pipeline
    assert (
        service.on_event.__func__
        is pipeline.on_native_event.__func__
    )

    assert service.on_retraction.__self__ is pipeline

    # Paper lifecycle also belongs to this exact pipeline instance.
    paper_task = next(
        task
        for task in runner.scheduler.jobs
        if task["name"] == "paper_manager"
    )

    assert paper_task["func"].__self__ is pipeline

    runner._stop_services()

    assert runner.services_started is False
    assert service.stopped == 1

    assert app["decision_authority"] is False
    assert app["live_authority"] is False
    assert app["execution_authority"] is False
