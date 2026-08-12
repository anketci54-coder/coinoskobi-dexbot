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
