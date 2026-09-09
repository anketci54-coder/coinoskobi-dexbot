from pathlib import Path

from app.pipeline.engine import PipelineEngine


class _CounterfactualStore:
    def __init__(self):
        self.context = None

    def observe(self, **kwargs):
        return {"state": "PENDING"}

    def record(self, **kwargs):
        self.context = kwargs["context"]
        return {
            "stored": True,
            "decision_id": 7,
        }

    def status(self):
        return {
            "size": 1,
            "outcome_counts": {},
        }


class _ProbeStore:
    def observe(self, **kwargs):
        return {"state": "OBSERVED"}

    def open_probe(self, **kwargs):
        return {
            "state": "EXISTS",
            "created": False,
        }


class _SnapshotStore:
    def capture(self, **kwargs):
        raise AssertionError("snapshot capture must not run")


def test_counterfactual_context_preserves_opportunity_diagnostics():
    engine = PipelineEngine.__new__(PipelineEngine)
    store = _CounterfactualStore()
    engine.counterfactual_store = store
    engine.watch_probe_store = _ProbeStore()
    engine.watch_probe_entry_snapshot_store = _SnapshotStore()

    result = engine.observe_counterfactual_candidate(
        {
            "token": "0xtoken",
            "pool": "0xpool",
            "price_usd": 1.25,
        },
        {
            "strategy": "PAPER_BUY",
            "unified": "WATCH",
            "paper": "WATCH",
            "reason": None,
            "opportunity_state": "WATCH",
            "opportunity_reason": "POSITIVE_CONTINUATION_NOT_ESTABLISHED",
            "hard_block": False,
            "score": 100.0,
            "confidence": 100.0,
            "sellability": "SELLABILITY_OK",
            "plan_blockers": [],
            "sizing_blockers": [],
            "market_context": {},
            "runtime_intelligence": {},
        },
        now=123.0,
    )

    assert result["record"]["decision_id"] == 7
    assert store.context["opportunity_state"] == "WATCH"
    assert (
        store.context["opportunity_reason"]
        == "POSITIVE_CONTINUATION_NOT_ESTABLISHED"
    )
    assert store.context["paper"] == "WATCH"
    assert store.context["reason"] is None


def test_run_cycle_exposes_score_opportunity_fields_and_logs_them():
    source = Path("app/pipeline/engine.py").read_text()

    assert '"opportunity_state": score.get(' in source
    assert '"opportunity_reason": score.get(' in source
    assert '"opportunity=%s opportunity_reason=%s "' in source
    assert 'summary["opportunity_state"]' in source
    assert 'summary["opportunity_reason"]' in source
