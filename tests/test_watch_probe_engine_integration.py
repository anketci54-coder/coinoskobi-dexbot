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


def test_watch_probe_open_captures_immutable_entry_snapshot(
    monkeypatch,
    tmp_path,
):
    from app.learning.watch_probe_entry_snapshot import (
        WatchProbeEntrySnapshotStore,
    )

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
    pipeline.watch_probe_store = WatchProbeStore(
        db_path
    )
    pipeline.watch_probe_entry_snapshot_store = (
        WatchProbeEntrySnapshotStore(db_path)
    )

    row = {
        "token": "0xabc",
        "pool": "0xdef",
        "price_usd": 1.0,
    }

    summary = {
        "paper": "WATCH",
        "strategy": "WATCH",
        "unified": "WATCH",
        "reason": None,
        "confidence": 33.33,
        "score": 33.33,
        "decision_history_id": 123,
        "market_context": {
            "liquidity_usd": 20000.0,
            "market_intelligence": {
                "volume_usd": 40000.0,
                "buys": 30,
                "participant_identity_coverage": 0.5,
            },
            "origin_participation": {
                "coverage": 0.4,
            },
            "runtime_market_flow": {
                "native_event_count": 8,
                "flow_intelligence": {
                    "coverage": 0.7,
                    "participant_identity_coverage": 0.6,
                },
                "stream_math": {
                    "state": "INSUFFICIENT",
                    "ewma": {
                        "ewma_volatility": None,
                    },
                },
            },
        },
        "runtime_intelligence": {
            "market_quality": {
                "volume_turnover": 2.0,
                "liquidity_state": "STABLE_OR_UNKNOWN",
                "market_evidence_ready": False,
                "participant_evidence_ready": False,
            },
            "market_regime": {
                "market_regime": "UNKNOWN",
            },
            "flow_confirmation": {
                "confirmation": "UNKNOWN",
            },
            "flow_quality": {
                "flow_quality": "UNKNOWN",
            },
            "flow_divergence": {
                "divergence_state": "UNKNOWN",
            },
        },
    }

    result = pipeline.observe_counterfactual_candidate(
        row,
        summary,
        now=1000.0,
    )

    assert result["probe_open"]["state"] == "OPENED"

    rows = (
        pipeline.watch_probe_entry_snapshot_store
        .snapshot(10)
    )

    assert len(rows) == 1

    snap = rows[0]

    assert snap["probe_id"] == result["probe_open"]["id"]
    assert snap["decision_history_id"] == result["record"].get(
        "decision_id"
    )
    assert snap["liquidity_usd"] == 20000.0
    assert snap["volume_usd"] == 40000.0
    assert snap["buys"] == 30
    assert snap["volatility_state"] == "UNKNOWN"


def test_watch_probe_links_real_decision_history_id(
    monkeypatch,
    tmp_path,
):
    from app.learning.watch_probe_entry_snapshot import (
        WatchProbeEntrySnapshotStore,
    )

    db_path = tmp_path / "paper.db"

    monkeypatch.setattr(
        engine_module,
        "PAPER_DB",
        Path(db_path),
    )

    pipeline = object.__new__(PipelineEngine)

    class LinkedCounterfactualStore:
        def observe(self, **kwargs):
            return {"state": "OBSERVED"}

        def record(self, **kwargs):
            return {
                "stored": True,
                "decision_id": 777,
                "transition_from": None,
            }

        def status(self):
            return {"state": "READY"}

    pipeline.counterfactual_store = LinkedCounterfactualStore()
    pipeline.watch_probe_store = WatchProbeStore(db_path)
    pipeline.watch_probe_entry_snapshot_store = (
        WatchProbeEntrySnapshotStore(db_path)
    )

    row = {
        "token": "0xabc",
        "pool": "0xdef",
        "price_usd": 1.0,
    }

    summary = {
        "paper": "WATCH",
        "strategy": "WATCH",
        "unified": "WATCH",
        "reason": None,
        "confidence": 33.33,
        "score": 33.33,
        "market_context": {},
        "runtime_intelligence": {},
    }

    result = pipeline.observe_counterfactual_candidate(
        row,
        summary,
        now=1000.0,
    )

    assert result["record"]["decision_id"] == 777

    probe_id = result["probe_open"]["id"]

    probe = pipeline.watch_probe_store._db.execute(
        """
        SELECT decision_history_id
        FROM watch_probe_trades
        WHERE id=?
        """,
        (probe_id,),
    ).fetchone()

    snap = (
        pipeline.watch_probe_entry_snapshot_store
        .snapshot(1)[0]
    )

    assert probe["decision_history_id"] == 777
    assert snap["decision_history_id"] == 777
