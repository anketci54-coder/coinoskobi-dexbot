import json
import threading
import time

import app.pipeline.fast_watch_revisit as module
from app.core.runner import Runner
from app.pipeline.fast_watch_revisit import FastWatchRevisitJob


TOKEN = "0x0000000000000000000000000000000000000001"
POOL = "0x0000000000000000000000000000000000000002"
QUOTE = "0x0000000000000000000000000000000000000003"


class _Candidate:
    def __init__(self, row):
        self.row = dict(row)

    def to_dict(self):
        return dict(self.row)


class _Store:
    def __init__(self, rows):
        self.rows = list(rows)

    def decision_snapshot(self, limit=100):
        return self.rows[:limit]


class _Scanner:
    def __init__(self, rows=None):
        self.rows = rows or [{
            "pool": POOL,
            "base_token": TOKEN,
            "quote_token": QUOTE,
        }]
        self.calls = []

    def pool_snapshots(self, pools, max_pools=30, persist_followups=True):
        self.calls.append((list(pools), max_pools, persist_followups))
        wanted = {str(value).lower() for value in pools}
        return [
            dict(row)
            for row in self.rows
            if str(row.get("pool") or "").lower() in wanted
        ]


class _Ingress:
    def __init__(self, *, active=True):
        self.active = active
        self.calls = []

    def classify_many(self, rows):
        self.calls.append(list(rows))
        return {
            "active": list(rows) if self.active else [],
            "deferred": [] if self.active else list(rows),
            "dropped": [],
            "stats": {
                "input": len(rows),
                "active": len(rows) if self.active else 0,
                "deferred": 0 if self.active else len(rows),
                "dropped": 0,
                "reasons": {},
            },
        }


class _PaperDB:
    def __init__(self, traded=None):
        self.traded = {
            str(value).lower()
            for value in (traded or [])
        }

    def has_trade_history(self, token):
        return str(token).lower() in self.traded


class _Flow:
    def __init__(self):
        self.confirmed = []

    def confirm_pair_membership(self, pool, token, quote):
        self.confirmed.append((pool, token, quote))
        return {"state": "VERIFIED"}


class _Pipeline:
    def __init__(self, rows, *, ingress_active=True, traded=None):
        self.counterfactual_store = _Store(rows)
        self.scanner = _Scanner()
        self.ingress_gate = _Ingress(active=ingress_active)
        self.paper_db = _PaperDB(traded=traded)
        self.native_market_flow = _Flow()
        self.runs = []
        self.observed = []
        self.intelligence = None

    def run(self, token, market_context=None):
        self.runs.append((token, dict(market_context or {})))
        return {
            "success": True,
            "data": {
                "strategy": {"decision": "PAPER_BUY"},
                "unified_decision": {"decision": "WATCH"},
                "paper": {"action": "WATCH", "reason": None},
                "unified_score": {
                    "score": 100.0,
                    "confidence": 100.0,
                    "opportunity_state": "WATCH",
                    "opportunity_reason": "ACTIVE_MOMENTUM_NOT_POSITIVE",
                },
                "risk_gate": {"hard_block": False},
                "analyzer_status": {
                    "sellability": {"status": "SELLABILITY_OK"},
                },
                "market_context": dict(market_context or {}),
                "runtime_intelligence": {},
            },
        }

    def observe_counterfactual_candidate(self, row, summary):
        self.observed.append((dict(row), dict(summary)))
        return {"record": {"stored": True}}


def _history_row(
    reason,
    *,
    hard_block=False,
    token=TOKEN,
    pool=POOL,
    action="WATCH",
    observed_at=None,
):
    return {
        "token": token,
        "pool": pool,
        "observed_at": (
            time.time() - 60
            if observed_at is None
            else observed_at
        ),
        "decision_action": action,
        "context_json": json.dumps({
            "strategy": "PAPER_BUY",
            "opportunity_state": "WATCH",
            "opportunity_reason": reason,
            "hard_block": hard_block,
        }),
    }


def _patch_normalization(monkeypatch):
    monkeypatch.setattr(
        module,
        "normalize_source_rows",
        lambda source, chain, source_rows: {
            "candidates": [
                _Candidate({
                    "chain": "bsc",
                    "token": TOKEN,
                    "pool": POOL,
                    "quote_token": QUOTE,
                })
            ]
        },
    )
    monkeypatch.setattr(
        module,
        "build_market_context",
        lambda row, runtime_feed=None: {},
    )


def test_fast_watch_selects_only_active_momentum_reasons(monkeypatch):
    rows = [
        _history_row("ACTIVE_MOMENTUM_NOT_POSITIVE"),
        _history_row("QUOTE_FLOW_NOT_SUPPORTING_MOVE", token="0x03", pool="0x04"),
        _history_row("POSITIVE_CONTINUATION_NOT_ESTABLISHED", hard_block=True, token="0x05", pool="0x06"),
    ]
    pipeline = _Pipeline(rows)
    _patch_normalization(monkeypatch)
    monkeypatch.setattr(
        FastWatchRevisitJob,
        "_refresh_local_sellability_evidence",
        lambda self, row: False,
    )

    job = FastWatchRevisitJob(pipeline, max_candidates=30)
    result = job._run_cycle_sync()

    assert result["state"] == "READY"
    assert result["selected"] == 1
    assert result["processed"] == 1
    assert result["failed"] == 0
    assert len(pipeline.runs) == 1
    assert len(pipeline.observed) == 1
    assert pipeline.observed[0][1]["opportunity_reason"] == (
        "ACTIVE_MOMENTUM_NOT_POSITIVE"
    )
    assert pipeline.native_market_flow.confirmed == [
        (POOL, TOKEN, QUOTE)
    ]
    assert pipeline.scanner.calls == [([POOL], 30, False)]
    assert result["bounded"] is True
    assert result["decision_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False


def test_fast_watch_is_strictly_bounded_and_deduplicated():
    rows = []
    for index in range(40):
        token = f"0x{index + 1:040x}"
        pool = f"0x{index + 100:040x}"
        rows.append(
            _history_row(
                "ACTIVE_PRICE_SERIES_NOT_READY",
                token=token,
                pool=pool,
            )
        )
    rows.insert(0, rows[0])

    pipeline = _Pipeline(rows)
    job = FastWatchRevisitJob(pipeline, max_candidates=30)

    identities = job._watched_identities()
    assert len(identities) == 30
    assert len(set(identities)) == 30
    assert job._status(state="READY")["max_candidates"] == 30


def test_newer_non_watch_transition_suppresses_older_watch():
    rows = [
        _history_row("STRUCTURAL_REJECT", action="REJECT"),
        _history_row("ACTIVE_MOMENTUM_NOT_POSITIVE", action="WATCH"),
    ]

    pipeline = _Pipeline(rows)
    job = FastWatchRevisitJob(pipeline)

    assert job._watched_identities() == []


def test_existing_trade_history_suppresses_old_watch():
    rows = [_history_row("ACTIVE_MOMENTUM_NOT_POSITIVE")]

    pipeline = _Pipeline(rows, traded=[TOKEN])
    job = FastWatchRevisitJob(pipeline)

    assert job._watched_identities() == []


def test_recent_watch_waits_for_configured_interval():
    rows = [
        _history_row(
            "ACTIVE_MOMENTUM_NOT_POSITIVE",
            observed_at=time.time(),
        )
    ]
    pipeline = _Pipeline(rows)
    job = FastWatchRevisitJob(pipeline)

    assert job._watched_identities() == []


def test_ingress_gate_must_still_be_active(monkeypatch):
    rows = [_history_row("ACTIVE_MOMENTUM_NOT_POSITIVE")]
    pipeline = _Pipeline(rows, ingress_active=False)
    _patch_normalization(monkeypatch)

    job = FastWatchRevisitJob(pipeline)
    result = job._run_cycle_sync()

    assert result["state"] == "NO_ACTIVE_WATCH_CANDIDATES"
    assert pipeline.ingress_gate.calls
    assert pipeline.runs == []


def test_missing_ingress_gate_fails_closed(monkeypatch):
    rows = [_history_row("ACTIVE_MOMENTUM_NOT_POSITIVE")]
    pipeline = _Pipeline(rows)
    del pipeline.ingress_gate
    _patch_normalization(monkeypatch)

    job = FastWatchRevisitJob(pipeline)
    result = job._run_cycle_sync()

    assert result["state"] == "NO_ACTIVE_WATCH_CANDIDATES"
    assert pipeline.runs == []


def test_missing_fresh_snapshot_provider_fails_closed():
    rows = [_history_row("ACTIVE_MOMENTUM_NOT_POSITIVE")]
    pipeline = _Pipeline(rows)
    del pipeline.scanner

    job = FastWatchRevisitJob(pipeline)
    result = job._run_cycle_sync()

    assert result["state"] == "NO_ACTIVE_WATCH_CANDIDATES"
    assert pipeline.runs == []


def test_local_evidence_refresh_preserves_provider_cache_age(monkeypatch):
    class Cache:
        def __init__(self):
            self.replaced = []

        def get(self, namespace, cache_key, ttl_seconds):
            return json.dumps({
                "success": True,
                "provider_success": True,
                "data": {
                    "sellable": True,
                    "local_evidence": {"completed": False},
                },
            })

        def replace_payload_preserve_age(self, namespace, cache_key, payload):
            self.replaced.append((namespace, cache_key, json.loads(payload)))
            return 1

    cache = Cache()
    monkeypatch.setattr(module.sellability_module, "_cache", cache)
    monkeypatch.setattr(
        module.sellability_module,
        "_local_evidence",
        lambda token, pair: {
            "completed": True,
            "exit_feasibility": {
                "spot_price_series_usd": [1.0, 1.1, 1.2],
            },
        },
    )

    job = FastWatchRevisitJob(_Pipeline([]))
    assert job._refresh_local_sellability_evidence({
        "token": TOKEN,
        "pool": POOL,
    }) is True

    assert len(cache.replaced) == 1
    payload = cache.replaced[0][2]
    assert payload["local_evidence_complete"] is True
    assert payload["data"]["local_evidence"]["completed"] is True


def test_run_cycle_dispatches_without_blocking(monkeypatch):
    pipeline = _Pipeline([])
    job = FastWatchRevisitJob(pipeline)
    entered = threading.Event()
    release = threading.Event()

    def slow_cycle():
        entered.set()
        release.wait(timeout=2)
        return job._status(state="READY")

    monkeypatch.setattr(job, "_run_cycle_sync", slow_cycle)

    first = job.run_cycle()
    assert first["state"] == "DISPATCHED"
    assert entered.wait(timeout=1)

    second = job.run_cycle()
    assert second["state"] == "BUSY"

    release.set()
    job._thread.join(timeout=1)
    assert not job._running


def test_runner_binds_fast_watch_at_twenty_second_cadence():
    pipeline = _Pipeline([])

    def scan_job():
        return pipeline

    runner = Runner(
        scan_job=scan_job,
        auxiliary_service_factory=lambda: [],
    )

    jobs = {
        job["name"]: job
        for job in runner.scheduler.jobs
    }

    assert jobs["scanner"]["interval"] == 300
    assert jobs["fast_watch_revisit"]["interval"] == 20
    assert runner.fast_watch_revisit.pipeline is pipeline


def test_runner_without_pipeline_capture_has_no_fast_watch_job():
    runner = Runner(
        scan_job=lambda: None,
        auxiliary_service_factory=lambda: [],
    )

    names = {
        job["name"]
        for job in runner.scheduler.jobs
    }

    assert "scanner" in names
    assert "fast_watch_revisit" not in names
    assert runner.fast_watch_revisit is None
