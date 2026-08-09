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
