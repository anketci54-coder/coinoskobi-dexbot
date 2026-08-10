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
        {"token": "bsc_0x0000000000000000000000000000000000000001"},
        {"token": "bsc_0x0000000000000000000000000000000000000002"},
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

    assert called == [
        "0x0000000000000000000000000000000000000001",
        "0x0000000000000000000000000000000000000002",
    ]
    assert engine.manager.called is True


def test_run_cycle_survives_manager_exception():
    engine = PipelineEngine.__new__(PipelineEngine)

    engine.cache = FakeCache([])
    engine.filter = FakeFilter()
    engine.manager = FakeManager(should_fail=True)

    engine.run_cycle()

    assert engine.manager.called is True
