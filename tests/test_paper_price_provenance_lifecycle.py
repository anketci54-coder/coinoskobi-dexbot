"""Entry and long-pass provenance regressions through the real PAPER gates."""
import copy
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.config.contracts import WBNB
from app.dex.open_position_hot_path import process_hot_positions
from app.paper.manager import PaperManager
from app.paper import manager as manager_module
from app.pipeline import engine
from app.risk import price_integrity as integrity
from price_integrity_support import POOL, TOKEN, V2RPC, evidence, position
from test_paper_candidate_pool_binding import lifecycle, successful_buy


@pytest.fixture
def entry(lifecycle, monkeypatch):
    job, state, candidate, db = lifecycle
    state["prices"] = [1, 1.04, 1.06]
    rows = [evidence(1.06)]
    job.pipeline.cache.all = lambda: copy.deepcopy(rows)
    job.pipeline.scanner = SimpleNamespace(
        pool_snapshots=lambda *a, **kw: copy.deepcopy(rows)
    )
    rpc = V2RPC(1.06)
    monkeypatch.setattr(integrity, "w3", rpc)
    buys = []

    def buy(**kwargs):
        buys.append(kwargs)
        return successful_buy(**kwargs)

    monkeypatch.setattr(engine, "_runtime_phase15h_buy_evidence", buy)
    return SimpleNamespace(job=job, candidate=candidate, db=db,
                           rows=rows, rpc=rpc, buys=buys)


def reject_evidence(rows, defect):
    row = rows[0]
    if defect == "missing":
        rows.clear()
    elif defect == "stale":
        row["observed_at"] = (datetime.now(timezone.utc) - timedelta(seconds=746)).isoformat()
    elif defect == "missing_time":
        row.pop("observed_at")
    elif defect == "future":
        row["observed_at"] = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    elif defect == "malformed":
        row["price_evidence_json"] = "{broken"
    elif defect == "nonobject":
        row["price_evidence_json"] = "[]"
    elif defect == "numeric_envelope":
        row["price_evidence_json"] = json.dumps(row)
        row["price_usd"] *= 1.01
    elif defect == "price_difference":
        row["price_usd"] *= 1.01
    else:
        key, value = {
            "pool": ("pool", "0x" + "33" * 20),
            "token": ("base_token", "0x" + "44" * 20),
            "quote": ("quote_token", WBNB),
            "source": ("source", "unknown"),
            "chain": ("chain", "ethereum"),
            "dex": ("dex", "pancakeswap_v3"),
        }[defect]
        row[key] = value


@pytest.mark.parametrize("defect", [
    "missing", "stale", "missing_time", "future", "malformed", "nonobject",
    "numeric_envelope", "pool", "token", "quote",
    "source", "chain", "dex",
])
def test_buy_success_cannot_insert_without_matching_entry_provenance(entry, defect):
    reject_evidence(entry.rows, defect)
    result = entry.job._process(entry.candidate)["data"]["paper"]

    assert len(entry.buys) == 1  # A successful BUY is insufficient.
    assert entry.db.open_positions() == []
    assert result["action"] != "PAPER_BUY"
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"


def test_verified_exact_entry_is_persisted_after_buy_success(entry):
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert result["action"] == "PAPER_BUY"
    stored = entry.db.open_positions()[0]
    opening = json.loads(stored["opening_context_json"])
    assert opening["phase15h_execution"]["buy"]["status"] == "SUCCESS"
    assert opening["price_observation"] == integrity.observation(entry.rows[0])
    assert opening["price_observation"]["price_usd"] == stored["entry_price"] == 1.06
    assert ("getReserves", POOL) in entry.rpc.calls  # Real admission verification.


def test_stored_entry_price_must_still_equal_observation(entry):
    assert entry.job._process(entry.candidate)["data"]["paper"]["action"] == "PAPER_BUY"
    stored = entry.db.open_positions()[0]
    stored["entry_price"] *= 1.01
    assert integrity.admission_check(stored) == {
        "state": "PRICE_UNVERIFIED", "reason": "ENTRY_EVIDENCE_MISSING",
    }


def test_entry_reads_evidence_published_during_buy_instead_of_earlier_copy(entry, monkeypatch):
    reject_evidence(entry.rows, "stale")
    published = evidence(1.06)

    def buy(**kwargs):
        entry.rows[:] = [published]
        return successful_buy(**kwargs)

    monkeypatch.setattr(engine, "_runtime_phase15h_buy_evidence", buy)
    assert entry.job._process(entry.candidate)["data"]["paper"]["action"] == "PAPER_BUY"
    stored = entry.db.open_positions()[0]
    assert json.loads(stored["opening_context_json"])["price_observation"] == integrity.observation(published)


@pytest.mark.parametrize("failure", ["rpc", "onchain_disagreement"])
def test_entry_requires_independent_price_verification(entry, failure):
    if failure == "rpc":
        entry.rpc.fail = True
    else:
        entry.rpc.price *= 2
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"
    assert entry.db.open_positions() == []


@pytest.mark.parametrize("status", ["REVERT", "UNKNOWN", None])
def test_fresh_entry_evidence_cannot_bypass_buy_failure(entry, monkeypatch, status):
    monkeypatch.setattr(engine, "_runtime_phase15h_buy_evidence",
                        lambda **kw: {"buy": {"status": status}})
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert result["reason"] == "PHASE15H_BUY_NOT_PROVEN"
    assert entry.db.open_positions() == []


def test_provenance_is_checked_after_slow_buy(entry, monkeypatch):
    def slow_buy(**kwargs):
        reject_evidence(entry.rows, "stale")
        return successful_buy(**kwargs)

    monkeypatch.setattr(engine, "_runtime_phase15h_buy_evidence", slow_buy)
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"
    assert entry.db.open_positions() == []


def test_evidence_expiring_during_independent_entry_proof_cannot_insert(entry, monkeypatch):
    now = datetime.now(timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    real_proof = integrity.PriceIntegrityGate._onchain

    def slow_proof(self, *args):
        nonlocal now
        result = real_proof(self, *args)
        now += timedelta(seconds=31)
        return result

    monkeypatch.setattr(integrity, "datetime", Clock)
    monkeypatch.setattr(integrity.PriceIntegrityGate, "_onchain", slow_proof)
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"
    assert entry.db.open_positions() == []


@pytest.mark.parametrize("cache_failure", ["stale", "locked"])
def test_entry_can_use_fresh_exact_pool_provider_evidence(entry, cache_failure):
    fresh = evidence(1.06)
    reject_evidence(entry.rows, "stale")
    if cache_failure == "locked":
        def locked():
            raise sqlite3.OperationalError("database is locked")
        entry.job.pipeline.cache.all = locked

    def snapshots(identities, *, persist_followups):
        assert len(entry.buys) == 1
        assert entry.db.open_positions() == []
        assert identities == [{"chain": "bsc", "pool": POOL,
                               "dex": "pancakeswap_v2", "token": TOKEN}]
        assert persist_followups is False
        return [evidence(9, pool="0x" + "33" * 20), fresh]

    entry.job.pipeline.scanner.pool_snapshots = snapshots
    assert entry.job._process(entry.candidate)["data"]["paper"]["action"] == "PAPER_BUY"
    stored = entry.db.open_positions()[0]
    assert json.loads(stored["opening_context_json"])["price_observation"] == integrity.observation(fresh)


def test_entry_provider_failure_cannot_insert(entry):
    reject_evidence(entry.rows, "stale")

    def unavailable(*args, **kwargs):
        raise ConnectionError("provider unavailable")

    entry.job.pipeline.scanner.pool_snapshots = unavailable
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"
    assert entry.db.open_positions() == []


@pytest.mark.parametrize("age,fresh", [(-1, False), (0, True), (30, True), (30.000001, False)])
def test_observation_freshness_preserves_thirty_second_boundary(monkeypatch, age, fresh):
    now = datetime.now(timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(integrity, "datetime", Clock)
    row = evidence(observed_at=(now - timedelta(seconds=age)).isoformat())
    assert integrity.MAX_AGE_SECONDS == 30
    assert integrity.observation_is_fresh(row) is fresh


@pytest.mark.parametrize("refresh_source", ["cache", "provider", "stale_provider"])
def test_later_position_observes_current_exact_pool_after_slow_position(monkeypatch, refresh_source):
    now = datetime.now(timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(integrity, "datetime", Clock)
    rows = [evidence(observed_at=now.isoformat())]
    initial_observed = rows[0]["observed_at"]
    rpc = V2RPC()
    manager = PaperManager.__new__(PaperManager)
    # Two position IDs isolate the per-position clock/reference contract.
    manager.db = SimpleNamespace(open_positions=lambda: [position(id=1), position(id=2)])
    manager.replay_closed_outcomes = lambda: None
    manager.price_integrity = integrity.PriceIntegrityGate(rpc)
    manager.price = SimpleNamespace(get_price=lambda _: pytest.fail("token-only fallback"))
    pipeline = engine.PipelineEngine.__new__(engine.PipelineEngine)
    pipeline.manager = manager
    pipeline.cache = SimpleNamespace(all=lambda: copy.deepcopy(rows))
    calls = []

    def snapshots(identities, *, persist_followups):
        assert identities == [{"chain": "bsc", "pool": POOL,
                               "dex": "pancakeswap_v2", "token": TOKEN}]
        assert persist_followups is False
        calls.append(identities)
        return [evidence(observed_at=(initial_observed if refresh_source == "stale_provider"
                                      else now.isoformat()))]

    pipeline.scanner = SimpleNamespace(pool_snapshots=snapshots)
    # Late binding makes the pre-patch failure exercise the old frozen reader.
    manager.price_observation_reader = lambda pos: pipeline._paper_price_observation(pos)
    reached = []

    def slow_strategy(pos, current, *args):
        nonlocal now
        reached.append(pos["id"])
        if pos["id"] == 1:
            now += timedelta(seconds=36)
            rpc.block["timestamp"] = int(now.timestamp())
            if refresh_source == "cache":
                rows[0] = evidence(observed_at=now.isoformat())
        return {"position_id": pos["id"], "price": current}

    manager._process_legacy_position = slow_strategy
    results = process_hot_positions(pipeline)
    if refresh_source == "stale_provider":
        assert reached == [1]
        assert results[-1] == {"state": "PRICE_UNVERIFIED",
                               "reason": "INVALID_PROVENANCE_OR_PRICE"}
        assert len(calls) == 1
    else:
        assert reached == [1, 2]
        assert results[-1] == {"position_id": 2, "price": 1.0}
        accepted = manager.price_integrity.accepted[(2, POOL, TOKEN, integrity.USDT.lower())]
        assert accepted["observed_at"].isoformat() == now.isoformat()
        assert len(calls) == (1 if refresh_source == "provider" else 0)


@pytest.mark.parametrize("defect", [
    "missing", "stale", "missing_time", "malformed", "nonobject",
    "numeric_envelope", "pool", "token", "quote", "source", "chain", "dex",
])
def test_runtime_reader_never_blesses_invalid_evidence(defect):
    rows = [evidence()]
    reject_evidence(rows, defect)
    pipeline = engine.PipelineEngine.__new__(engine.PipelineEngine)
    pipeline.cache = SimpleNamespace(all=lambda: copy.deepcopy(rows))
    pipeline.scanner = SimpleNamespace(pool_snapshots=lambda *a, **k: copy.deepcopy(rows))
    manager = PaperManager.__new__(PaperManager)
    manager.price = SimpleNamespace(get_price=lambda _: pytest.fail("token-only fallback"))
    manager.price_observation_reader = pipeline._paper_price_observation
    manager.price_integrity = integrity.PriceIntegrityGate(V2RPC())
    manager._process_legacy_position = lambda *a: pytest.fail("invalid price reached strategy")
    pos = position()
    before = copy.deepcopy(pos)

    assert manager._process_position(pos)["state"].startswith("PRICE_")
    assert pos == before
    assert not manager.price_integrity.accepted


def test_runtime_provider_failure_does_not_fall_back_to_frozen_snapshot():
    pipeline = engine.PipelineEngine.__new__(engine.PipelineEngine)
    rows = [evidence()]
    reject_evidence(rows, "stale")
    pipeline.cache = SimpleNamespace(all=lambda: rows)

    def unavailable(*a, **kw):
        raise ConnectionError("provider unavailable")

    pipeline.scanner = SimpleNamespace(pool_snapshots=unavailable)
    manager = PaperManager.__new__(PaperManager)
    manager.price_observation_reader = pipeline._paper_price_observation
    manager.price = SimpleNamespace(get_observation=lambda _: evidence())
    manager.price_integrity = integrity.PriceIntegrityGate(V2RPC())
    manager._process_legacy_position = lambda *a: pytest.fail("reader failure reached strategy")
    assert manager._process_position(position()) == {
        "state": "PRICE_UNVERIFIED", "reason": "OBSERVATION_UNAVAILABLE",
    }


def test_engine_constructed_manager_uses_exact_reader_through_hot_path(monkeypatch):
    # Isolate filesystem-owning dependencies; keep the actual composition,
    # manager, hot reader, and independent integrity gate.
    db = SimpleNamespace(open_positions=lambda: [position()])
    numeric_only = SimpleNamespace(get_price=lambda _: pytest.fail("token fallback"))
    for module in (engine, manager_module):
        monkeypatch.setattr(module, "PaperDatabase", lambda: db)
        monkeypatch.setattr(module, "CachePrice", lambda: numeric_only)
    for name in ("RuntimeLearningOutcomeFeed", "CounterfactualObservationStore",
                 "UniverseRegistry", "HotDeepPathRouter"):
        monkeypatch.setattr(engine, name, lambda *a, **kw: SimpleNamespace())
    monkeypatch.setattr(engine, "GeckoCache", lambda: SimpleNamespace(all=lambda: [evidence()]))
    monkeypatch.setattr(engine, "GeckoScanner", lambda: SimpleNamespace())
    pipeline = engine.PipelineEngine()
    manager = pipeline.manager
    manager.replay_closed_outcomes = lambda: None
    manager.price_integrity = integrity.PriceIntegrityGate(V2RPC())
    manager._process_legacy_position = lambda pos, current, *a: current
    # The cache is repaired after the hot reader captures a mismatched envelope.
    # Only the constructor-bound reader can see that repair during evaluation.
    reads = iter([
        [{**evidence(), "price_evidence_json": json.dumps(evidence(2))}],
        [evidence()],
    ])
    pipeline.cache.all = lambda: next(reads)
    assert process_hot_positions(pipeline) == [1.0]
    assert len(manager.price_integrity.accepted) == 1


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("trade_type", ["LEGACY", "NORMAL", "VUR_KAC"])
def test_runtime_evidence_expiring_during_rpc_cannot_mutate(monkeypatch, warm, trade_type):
    now = datetime.now(timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(integrity, "datetime", Clock)
    rpc = V2RPC()
    gate = integrity.PriceIntegrityGate(rpc)
    pos = position()
    if trade_type != "LEGACY":
        pos["trade_type"] = trade_type
        pos["mathematical_plan_json"] = json.dumps({
            "contract": "mathematical_trade_plan", "trade_type": trade_type,
        })
    if warm:
        gate.accept(gate.evaluate(pos, evidence(observed_at=now.isoformat())))
    references_before = copy.deepcopy(gate.accepted)
    position_before = copy.deepcopy(pos)
    now += timedelta(seconds=1)
    rpc.price *= 2
    row = evidence(2, observed_at=now.isoformat())
    real_proof = gate._onchain

    def slow_proof(*args):
        nonlocal now
        result = real_proof(*args)
        now += timedelta(seconds=31)
        return result

    monkeypatch.setattr(gate, "_onchain", slow_proof)
    manager = PaperManager.__new__(PaperManager)
    manager.price_integrity = gate
    manager.price = SimpleNamespace(get_observation=lambda _: row)

    def strategy(*args):
        pytest.fail("expired observation reached strategy mutation")

    manager._process_legacy_position = strategy
    manager._process_normal_math_position = strategy
    manager._process_vur_kac_position = strategy
    assert manager._process_position(pos) == {
        "state": "PRICE_UNVERIFIED", "reason": "INVALID_PROVENANCE_OR_PRICE",
    }
    assert pos == position_before
    assert gate.accepted == references_before
