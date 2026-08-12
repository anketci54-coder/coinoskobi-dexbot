from app.pipeline.intelligence_composition import (
    RuntimeIntelligenceComposition,
)


def test_pipeline_engine_declares_runtime_composition():
    from pathlib import Path

    s = Path(
        "app/pipeline/engine.py"
    ).read_text()

    assert (
        "RuntimeIntelligenceComposition"
        in s
    )

    assert (
        "self.intelligence"
        in s
    )

    assert (
        '"runtime_intelligence"'
        in s
    )


def test_runtime_composition_is_context_only():
    c = RuntimeIntelligenceComposition()

    result = c.build(
        "0xtoken",
        market_input={
            "volume_usd": 1000,
            "liquidity_usd": 5000,
        },
    )

    assert result[
        "context_only"
    ] is True

    assert result[
        "can_upgrade_candidate"
    ] is False

    assert result[
        "hard_safety_override_allowed"
    ] is False


def test_pipeline_lazy_intelligence_supports_new_without_init(
    monkeypatch,
):
    import app.pipeline.engine as pipeline_module
    from app.pipeline.engine import PipelineEngine

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
            "data": {},
        },
    )

    result = engine.run(
        "0x0000000000000000000000000000000000000001"
    )

    assert hasattr(
        engine,
        "intelligence",
    )

    runtime = result[
        "data"
    ]["runtime_intelligence"]

    assert runtime[
        "context_only"
    ] is True

    assert runtime[
        "decision_authority"
    ] is False


def test_runtime_intelligence_does_not_mutate_market_context(
    monkeypatch,
):
    import app.pipeline.engine as pipeline_module
    from app.pipeline.engine import PipelineEngine

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
            "data": {},
        },
    )

    context = {
        "liquidity_usd": 8000,
        "trade_size_usd": None,
        "price_impact_pct": None,
        "slippage_pct": None,
    }

    original = dict(context)

    result = engine.run(
        "0x0000000000000000000000000000000000000001",
        market_context=context,
    )

    assert context == original

    assert (
        result["data"]["market_context"]
        == original
    )

    assert (
        "runtime_intelligence"
        in result["data"]
    )

    assert (
        "runtime_intelligence"
        not in result["data"]["market_context"]
    )
