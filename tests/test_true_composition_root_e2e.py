import asyncio
import importlib

import app.paper.database as paper_database_module
import app.pipeline.engine as pipeline_module
from app.config.contracts import WBNB
from app.dex.native_ingestion import SWAP_TOPIC
from app.dex.transaction_origin import TransactionOriginResolver
from app.paper.database import PaperDatabase

PAIR = "0x00000000000000000000000000000000000000aa"
TOKEN = "0x0000000000000000000000000000000000000001"
WALLET = "0x0000000000000000000000000000000000000123"


def word(value):
    return f"{value:064x}"


EVENT = {"state": "NORMALIZED", "event_type": "SWAP", "event_identity": "0xaaa:0x1", "transaction_hash": "0xaaa", "log_index": "0x1", "block_number": "0x10", "removed": False, "address": PAIR, "topics": [SWAP_TOPIC], "data": "0x" + word(0) + word(10) + word(5) + word(0)}


class EventingService:
    def __init__(self, url, pair):
        self.url, self.pair = url, pair
        self.on_event = self.on_retraction = None
        self.started = self.stopped = 0

    def bind_callbacks(self, *, on_event=None, on_retraction=None):
        self.on_event, self.on_retraction = on_event, on_retraction
        return {"state": "BOUND"}

    def start(self):
        self.started += 1
        asyncio.run(self.on_event(dict(EVENT)))
        return True

    def stop(self):
        self.stopped += 1
        return True

    def status(self):
        return {"state": "READY"}


class CacheRows:
    def all(self):
        return [{"pool": PAIR, "base_token": f"bsc_{TOKEN}", "quote_token": f"bsc_{WBNB}", "dex": "pancakeswap_v2", "liquidity": 100000, "volume_24h": 250000, "buys_24h": 100, "fdv": 1000000, "price_usd": 1.0, "created_at": None}]
    def replace(self, row): return None
    def prune_except(self, pools, preserve_tokens=None): return 0


class PassIngress:
    def classify(self, row, now=None): return {"lane": "ACTIVE", "reason": "TEST_PASS", "row": dict(row)}
    def classify_many(self, rows):
        rows = list(rows)
        return {"active": rows, "stats": {"input": len(rows), "active": len(rows), "deferred": 0, "dropped": 0}}


class PassConveyor:
    def label_many(self, rows):
        rows = list(rows)
        return {"rows": rows, "stats": {"warm": 0, "partial": 0, "cold": len(rows)}}


class OpenPrice:
    def get_price(self, token): return 1.0


class StopHitPrice:
    def get_price(self, token): return 0.80


def _analysis_stubs(monkeypatch):
    monkeypatch.setattr(pipeline_module, "token_analyze", lambda _: {"success": True, "data": {"symbol": "OCR"}})
    monkeypatch.setattr(pipeline_module, "pair_analyze", lambda _: {"success": True, "data": {"exists": False, "pair": None, "quote_ok": False}})
    monkeypatch.setattr(pipeline_module, "risk_analyze", lambda _: {"success": True, "data": {}})
    monkeypatch.setattr(pipeline_module._risk_gate, "evaluate", lambda _: {"hard_block": False, "hard_block_reasons": []})
    monkeypatch.setattr(pipeline_module._strategy, "evaluate", lambda *_: {"data": {"decision": "PAPER_BUY", "paper_trade": True, "score": 100, "reasons": []}})
    monkeypatch.setattr(pipeline_module._unified_decision, "evaluate", lambda _: {"decision": "PAPER_BUY_CANDIDATE", "decision_authority": False, "paper_authority": False, "live_authority": False, "wallet_authority": False, "execution_authority": False})


def test_true_composition_root_e2e(monkeypatch, tmp_path):
    """Runner -> paper entry -> persisted stop hit -> close -> learning feed."""
    module = importlib.import_module("main")
    monkeypatch.setattr(module, "WSS_URL", "wss://provider")
    monkeypatch.setattr(module, "WSS_PAIR", PAIR)
    monkeypatch.setattr(module, "WSS_TOKEN", TOKEN)

    db_path = tmp_path / "paper_e2e.db"
    monkeypatch.setattr(paper_database_module, "DB", db_path)
    PaperDatabase._instance = None
    PaperDatabase._initialized = False
    _analysis_stubs(monkeypatch)

    app = module.build_application(wss_service_factory=EventingService)
    pipeline, runner, service = app["pipeline"], app["runner"], app["services"][0]
    pipeline.cache = CacheRows()
    pipeline.ingress_gate = PassIngress()
    pipeline.conveyor = PassConveyor()
    pipeline.price = OpenPrice()
    pipeline.manager.price = StopHitPrice()
    pipeline.native_actor_intelligence.resolver = TransactionOriginResolver(fetcher=lambda _: {"from": WALLET})

    runner.sleep_func = lambda _: runner.stop()
    runner.run()

    assert service.started == 1
    assert service.stopped == 1
    assert runner.services_started is False
    actor = pipeline.native_actor_intelligence.snapshot(PAIR)
    assert actor["state"] == "READY"
    assert actor["wallet_id"] == f"bsc:{WALLET}"

    closed = pipeline.paper_db.closed_positions()
    assert len(closed) == 1
    assert closed[0]["token"].lower() == TOKEN.lower()
    assert closed[0]["status"] == "CLOSED"
    assert closed[0]["close_reason"] == "PERSISTED_STOP_LOSS"
    assert float(closed[0]["exit_price"]) == 0.80
    assert float(closed[0]["sl_price"]) > 0.80
    assert closed[0]["opening_context_json"]
    assert "\"captured_at_entry\":true" in closed[0]["opening_context_json"]

    learning = pipeline.learning_outcome_feed.calibration_snapshot()
    assert learning["state"] == "READY"
    assert learning["payload"]["proposal_only"] is True
    assert learning["payload"]["automatic_apply_allowed"] is False
    assert app["decision_authority"] is False
    assert app["live_authority"] is False
    assert app["execution_authority"] is False

    pipeline.paper_db.conn.close()
    PaperDatabase._instance = None
    PaperDatabase._initialized = False
