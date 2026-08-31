from pathlib import Path

import app.pipeline.engine as engine_module
from app.learning.watch_probe_store import WatchProbeStore
from app.pipeline.engine import PipelineEngine


class FakeCounterfactualStore:
    def observe(self, **kwargs):
        return {"state": "OBSERVED"}

    def record(self, **kwargs):
        return {
            "state": "RECORDED",
            "stored": True,
        }

    def status(self):
        return {"state": "READY"}


def test_watch_opens_exactly_one_isolated_probe(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "paper.db"

    monkeypatch.setattr(
        engine_module,
        "PAPER_DB",
        Path(db_path),
    )

    pipeline = object.__new__(PipelineEngine)

    pipeline.counterfactual_store = (
        FakeCounterfactualStore()
    )

    pipeline.watch_probe_store = (
        WatchProbeStore(db_path)
    )

    row = {
        "token": "0xabc",
        "pool": "0xdef",
        "price_usd": 0.25,
    }

    summary = {
        "paper": "WATCH",
        "strategy": "WATCH",
        "unified": "INSUFFICIENT",
        "reason": "PLAN_BLOCKED",
    }

    first = pipeline.observe_counterfactual_candidate(
        row,
        summary,
        now=1000.0,
    )

    second = pipeline.observe_counterfactual_candidate(
        row,
        summary,
        now=1010.0,
    )

    assert first["probe_open"]["state"] == "OPENED"
    assert first["probe_open"]["created"] is True
    assert first["probe_open"]["entry_usdt"] == 1.0

    assert second["probe_open"]["state"] == "ALREADY_EXISTS"
    assert second["probe_open"]["created"] is False

    rows = pipeline.watch_probe_store.snapshot(10)

    assert len(rows) == 1

    probe = rows[0]

    assert probe["token"] == "0xabc"
    assert probe["pool"] == "0xdef"
    assert probe["entry_usdt"] == 1.0
    assert probe["entry_price"] == 0.25
    assert probe["token_amount"] == 4.0
    assert probe["status"] == "OPEN"


def test_reject_does_not_open_watch_probe(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "paper.db"

    monkeypatch.setattr(
        engine_module,
        "PAPER_DB",
        Path(db_path),
    )

    pipeline = object.__new__(PipelineEngine)

    pipeline.counterfactual_store = (
        FakeCounterfactualStore()
    )

    pipeline.watch_probe_store = (
        WatchProbeStore(db_path)
    )

    result = pipeline.observe_counterfactual_candidate(
        {
            "token": "0xaaa",
            "pool": "0xbbb",
            "price_usd": 1.0,
        },
        {
            "paper": "REJECT",
            "strategy": "REJECT",
            "unified": "REJECT",
            "reason": "HARD_BLOCK",
        },
        now=1000.0,
    )

    assert result["probe_open"]["state"] == "NOT_WATCH"
    assert result["probe_open"]["created"] is False

    assert pipeline.watch_probe_store.snapshot(10) == []
