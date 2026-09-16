import app.pipeline.engine as engine_module
from app.pipeline.engine import PipelineEngine


class _PaperFeed:
    def event_snapshot(self):
        return [{"source": "paper"}]


class _CounterfactualStore:
    def outcome_snapshot(self):
        return [{"source": "short"}]

    def durable_snapshot(self, *, limit=100):
        assert limit == 512
        return [{"source": "durable"}]


def test_unified_outcome_snapshot_feeds_bounded_durable_phase13c_rows(
    monkeypatch,
):
    captured = {}

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return {"state": "READY"}

    monkeypatch.setattr(
        engine_module,
        "build_unified_outcome_readmodel",
        fake_builder,
    )

    engine = object.__new__(PipelineEngine)
    engine.learning_outcome_feed = _PaperFeed()
    engine.counterfactual_store = _CounterfactualStore()

    result = engine.unified_outcome_snapshot()

    assert result == {"state": "READY"}
    assert captured["paper_events"] == [
        {"source": "paper"}
    ]
    assert captured["counterfactual_events"] == [
        {"source": "short"}
    ]
    assert captured[
        "durable_counterfactual_events"
    ] == [{"source": "durable"}]


def test_unified_outcome_snapshot_tolerates_store_without_durable_reader(
    monkeypatch,
):
    captured = {}

    class LegacyStore:
        def outcome_snapshot(self):
            return []

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return {"state": "INSUFFICIENT"}

    monkeypatch.setattr(
        engine_module,
        "build_unified_outcome_readmodel",
        fake_builder,
    )

    engine = object.__new__(PipelineEngine)
    engine.learning_outcome_feed = _PaperFeed()
    engine.counterfactual_store = LegacyStore()

    engine.unified_outcome_snapshot()

    assert captured[
        "durable_counterfactual_events"
    ] == []
