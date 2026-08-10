import app.pipeline.engine as pipeline_module
from app.pipeline.engine import PipelineEngine


def test_pipeline_methods_exist():
    engine = PipelineEngine.__new__(PipelineEngine)

    assert hasattr(engine, "run")
    assert hasattr(engine, "run_cycle")


def test_pipeline_uses_real_pair_result_when_pair_missing(monkeypatch):
    engine = PipelineEngine.__new__(PipelineEngine)

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {"success": True, "data": {}},
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {
                "code_size": 0,
                "owner": False,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": False,
                "pair": None,
                "quote_ok": False,
            },
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["data"]["pair"]["exists"] is False
    assert result["data"]["pair"]["pair"] is None
    assert result["data"]["pair"]["quote_ok"] is False
    assert result["data"]["strategy"]["score"] == 45
    assert result["data"]["strategy"]["decision"] == "REJECT"


def test_pipeline_uses_real_pair_result_when_pair_exists(monkeypatch):
    engine = PipelineEngine.__new__(PipelineEngine)

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {"success": True, "data": {}},
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {
                "code_size": 0,
                "owner": False,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": True,
                "pair": "0x0000000000000000000000000000000000000002",
                "quote_ok": True,
            },
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["data"]["pair"]["exists"] is True
    assert result["data"]["pair"]["quote_ok"] is True
    assert result["data"]["strategy"]["score"] == 80
    assert result["data"]["strategy"]["decision"] == "WATCH"


def test_pipeline_exposes_analyzer_status(monkeypatch):
    engine = PipelineEngine.__new__(PipelineEngine)

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {
            "success": False,
            "error": "token rpc failed",
            "data": {},
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": False,
                "pair": None,
                "quote_ok": False,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": False,
            "error": "risk rpc failed",
            "data": {},
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    status = result["data"]["analyzer_status"]

    assert status["token"]["status"] == "TOKEN_UNKNOWN"
    assert status["token"]["error"] == "token rpc failed"

    assert status["pair"]["status"] == "PAIR_OK"
    assert status["pair"]["error"] is None

    assert status["risk"]["status"] == "RISK_UNKNOWN"
    assert status["risk"]["error"] == "risk rpc failed"

    assert result["data"]["strategy"]["decision"] == "REJECT"


def test_pipeline_exposes_all_analyzers_ok(monkeypatch):
    engine = PipelineEngine.__new__(PipelineEngine)

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {
            "success": True,
            "data": {"name": "Example Token"},
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": True,
                "pair": "0x0000000000000000000000000000000000000002",
                "quote_ok": True,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {
                "code_size": 0,
                "owner": False,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    status = result["data"]["analyzer_status"]

    assert status["token"]["status"] == "TOKEN_OK"
    assert status["pair"]["status"] == "PAIR_OK"
    assert status["risk"]["status"] == "RISK_OK"


class FakeCache:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeFilter:
    def filter(self, rows):
        return rows


class FakeManager:
    def __init__(self, should_fail=False):
        self.called = False
        self.should_fail = should_fail

    def process(self):
        self.called = True
        if self.should_fail:
            raise RuntimeError("manager failed")


def test_run_cycle_continues_after_single_token_exception():
    engine = PipelineEngine.__new__(PipelineEngine)

    engine.cache = FakeCache([
        {
            "pool": "0x0000000000000000000000000000000000000101",
            "token": "bsc_0x0000000000000000000000000000000000000001",
            "quote_token": "bsc_0x00000000000000000000000000000000000000ff",
            "dex": "pancakeswap_v2",
            "liquidity": 20_001,
            "volume_24h": 5_001,
            "buys_24h": 21,
            "fdv": 100_001,
            "price_usd": 0.001,
            "created_at": None,
        },
        {
            "pool": "0x0000000000000000000000000000000000000102",
            "token": "bsc_0x0000000000000000000000000000000000000002",
            "quote_token": "bsc_0x00000000000000000000000000000000000000ff",
            "dex": "pancakeswap_v2",
            "liquidity": 20_002,
            "volume_24h": 5_002,
            "buys_24h": 22,
            "fdv": 100_002,
            "price_usd": 0.001,
            "created_at": None,
        },
    ])
    engine.filter = FakeFilter()
    engine.manager = FakeManager()

    called = []

    def fake_run(token):
        called.append(token)

        if token.endswith("1"):
            raise RuntimeError("token failed")

        return {"success": True}

    engine.run = fake_run

    engine.run_cycle()

    assert set(called) == {
        "0x0000000000000000000000000000000000000001",
        "0x0000000000000000000000000000000000000002",
    }

    assert len(called) == 2
    assert engine.manager.called is True


def test_run_cycle_survives_manager_exception():
    engine = PipelineEngine.__new__(PipelineEngine)

    engine.cache = FakeCache([])
    engine.filter = FakeFilter()
    engine.manager = FakeManager(should_fail=True)

    engine.run_cycle()

    assert engine.manager.called is True


def test_honeypot_hard_block_overrides_high_strategy_score(
    monkeypatch,
):
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {
            "success": True,
            "data": {
                "name": "Example Token",
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": True,
                "pair": (
                    "0x000000000000000000000000"
                    "0000000000000002"
                ),
                "quote_ok": True,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {
                "code_size": 7000,
                "owner": False,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
                "honeypot": True,
                "sellable": False,
            },
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    assert (
        result["data"]["risk_gate"][
            "hard_block"
        ]
        is True
    )

    assert (
        result["data"]["strategy"][
            "decision"
        ]
        == "REJECT"
    )

    assert (
        result["data"]["strategy"][
            "paper_trade"
        ]
        is False
    )

    assert any(
        reason.startswith(
            "HARD_BLOCK:"
        )
        for reason in (
            result["data"]["strategy"][
                "reasons"
            ]
        )
    )


def test_sellability_check_skipped_for_reject(
    monkeypatch,
):
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    called = []

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {
            "success": True,
            "data": {},
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": False,
                "pair": None,
                "quote_ok": False,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {},
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "sellability_analyze",
        lambda *args, **kwargs: (
            called.append(True)
        ),
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    assert called == []

    assert (
        result["data"][
            "analyzer_status"
        ]["sellability"]["status"]
        == "SELLABILITY_SKIPPED"
    )


def test_confirmed_deep_honeypot_blocks_entry(
    monkeypatch,
):
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {
            "success": True,
            "data": {
                "name": "Example",
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": True,
                "pair": (
                    "0x000000000000000000000000"
                    "0000000000000002"
                ),
                "quote_ok": True,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {
                "code_size": 7000,
                "owner": False,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "sellability_analyze",
        lambda *args, **kwargs: {
            "success": True,
            "source": "sellability",
            "error": None,
            "data": {
                "honeypot": True,
                "sellable": False,
                "sellability_checked": True,
            },
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    assert (
        result["data"][
            "risk_gate"
        ]["hard_block"]
        is True
    )

    assert (
        result["data"][
            "strategy"
        ]["decision"]
        == "REJECT"
    )

    assert (
        result["data"][
            "strategy"
        ]["paper_trade"]
        is False
    )


def test_sellability_provider_failure_does_not_convict(
    monkeypatch,
):
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {
            "success": True,
            "data": {
                "name": "Example",
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": True,
                "pair": (
                    "0x000000000000000000000000"
                    "0000000000000002"
                ),
                "quote_ok": True,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {
                "code_size": 7000,
                "owner": False,
                "mint": False,
                "pause": False,
                "blacklist": False,
                "max_tx": False,
                "max_wallet": False,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "sellability_analyze",
        lambda *args, **kwargs: {
            "success": False,
            "source": "sellability",
            "error": "timeout",
            "data": {
                "honeypot": None,
                "sellable": None,
            },
        },
    )

    # Avoid touching paper database.
    class FakePaperDB:
        def has_open_position(
            self,
            token,
        ):
            return True

    engine.paper_db = FakePaperDB()

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    assert (
        result["data"][
            "risk_gate"
        ]["hard_block"]
        is False
    )

    assert (
        result["data"][
            "analyzer_status"
        ]["sellability"]["status"]
        == "SELLABILITY_UNKNOWN"
    )


def test_pipeline_exposes_trap_risk_without_new_authority(
    monkeypatch,
):
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    monkeypatch.setattr(
        pipeline_module,
        "token_analyze",
        lambda _: {
            "success": True,
            "data": {},
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "pair_analyze",
        lambda _: {
            "success": True,
            "data": {
                "exists": False,
                "pair": None,
                "quote_ok": False,
            },
        },
    )

    monkeypatch.setattr(
        pipeline_module,
        "risk_analyze",
        lambda _: {
            "success": True,
            "data": {
                "mint": True,
                "blacklist": True,
            },
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    trap = result["data"][
        "trap_risk"
    ]

    assert trap[
        "trade_authority"
    ] is False

    assert trap[
        "hard_block"
    ] is False

    assert trap[
        "signal_count"
    ] >= 2

    assert result["data"][
        "strategy"
    ]["decision"] == "REJECT"
