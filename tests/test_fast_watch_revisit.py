import json
import threading
import time

import app.pipeline.fast_watch_revisit as module
from app.core.runner import Runner
from app.pipeline.fast_watch_revisit import FastWatchRevisitJob


TOKEN = "0x0000000000000000000000000000000000000001"
POOL = "0x0000000000000000000000000000000000000002"
QUOTE = "0x0000000000000000000000000000000000000003"
ANALYSIS_PAIR = "0x0000000000000000000000000000000000000004"


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
    assert pipeline.scanner.calls == [([POOL], 1, False)]
    assert result["bounded"] is True
    assert result["decision_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False


def test_fast_watch_overfetch_is_bounded_and_deduplicated():
    rows = []
    for index in range(400):
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
    assert len(identities) == 240
    assert len(set(identities)) == 240
    assert job._status(state="READY")["max_candidates"] == 30


def test_fresh_rows_batches_provider_calls_and_caps_after_ingress(monkeypatch):
    identities = []
    scanner_rows = []
    for index in range(65):
        token = f"0x{index + 1:040x}"
        pool = f"0x{index + 1000:040x}"
        identities.append((token.lower(), pool.lower()))
        scanner_rows.append({
            "pool": pool,
            "base_token": token,
            "quote_token": QUOTE,
        })

    pipeline = _Pipeline([])
    pipeline.scanner = _Scanner(scanner_rows)

    def normalize(source, chain, source_rows):
        row = source_rows[0]
        return {
            "candidates": [
                _Candidate({
                    "chain": "bsc",
                    "token": row["base_token"],
                    "pool": row["pool"],
                    "quote_token": row["quote_token"],
                })
            ]
        }

    monkeypatch.setattr(module, "normalize_source_rows", normalize)

    job = FastWatchRevisitJob(pipeline, max_candidates=30)
    fresh = job._fresh_rows(identities)

    assert len(fresh) == 30
    assert len(pipeline.scanner.calls) == 1
    pools, max_pools, persist = pipeline.scanner.calls[0]
    assert len(pools) == 30
    assert max_pools == 30
    assert persist is False


def test_fresh_rows_isolates_unsupported_dex_without_losing_valid_pool(
    monkeypatch,
):
    bad_token = "0x0000000000000000000000000000000000000011"
    bad_pool = "0x0000000000000000000000000000000000000012"
    good_token = "0x0000000000000000000000000000000000000021"
    good_pool = "0x0000000000000000000000000000000000000022"

    class _MixedDexScanner:
        def __init__(self):
            self.calls = []

        def pool_snapshots(
            self,
            pools,
            max_pools=30,
            persist_followups=True,
        ):
            pools = [str(value).lower() for value in pools]
            self.calls.append(list(pools))

            if bad_pool.lower() in pools:
                raise ValueError("unsupported DEX")

            if good_pool.lower() in pools:
                return [{
                    "pool": good_pool,
                    "base_token": good_token,
                    "quote_token": QUOTE,
                }]

            return []

    def normalize(source, chain, source_rows):
        row = source_rows[0]
        return {
            "candidates": [
                _Candidate({
                    "chain": "bsc",
                    "token": row["base_token"],
                    "pool": row["pool"],
                    "quote_token": row["quote_token"],
                })
            ]
        }

    pipeline = _Pipeline([])
    pipeline.scanner = _MixedDexScanner()
    monkeypatch.setattr(module, "normalize_source_rows", normalize)

    job = FastWatchRevisitJob(pipeline, max_candidates=30)

    fresh = job._fresh_rows([
        (bad_token.lower(), bad_pool.lower()),
        (good_token.lower(), good_pool.lower()),
    ])

    assert len(fresh) == 1
    assert fresh[0]["token"] == good_token
    assert fresh[0]["pool"] == good_pool

    assert pipeline.scanner.calls == [
        [bad_pool.lower(), good_pool.lower()],
        [bad_pool.lower()],
        [good_pool.lower()],
    ]


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


def test_local_evidence_refresh_uses_analysis_pair_and_cas(monkeypatch):
    class Cache:
        def __init__(self):
            self.replaced = []

        def get_versioned(self, namespace, cache_key, ttl_seconds):
            assert cache_key.endswith(ANALYSIS_PAIR.lower())
            return {
                "payload": json.dumps({
                    "success": True,
                    "provider_success": True,
                    "data": {
                        "sellable": True,
                        "local_evidence": {"completed": False},
                    },
                }),
                "updated_at": 1234.5,
            }

        def replace_payload_if_version(
            self,
            namespace,
            cache_key,
            payload,
            expected_updated_at,
        ):
            self.replaced.append((
                namespace,
                cache_key,
                json.loads(payload),
                expected_updated_at,
            ))
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
    monkeypatch.setattr(
        module.pair_module,
        "analyze",
        lambda token: {
            "success": True,
            "data": {
                "exists": True,
                "pair": ANALYSIS_PAIR,
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
    assert cache.replaced[0][3] == 1234.5


def test_local_evidence_refresh_does_not_fallback_to_candidate_pool(monkeypatch):
    monkeypatch.setattr(
        module.pair_module,
        "analyze",
        lambda token: {
            "success": True,
            "data": {"exists": False, "pair": None},
        },
    )

    job = FastWatchRevisitJob(_Pipeline([]))
    assert job._refresh_local_sellability_evidence({
        "token": TOKEN,
        "pool": POOL,
    }) is False


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


def test_shutdown_waits_for_inflight_worker(monkeypatch):
    pipeline = _Pipeline([])
    job = FastWatchRevisitJob(pipeline)
    entered = threading.Event()
    release = threading.Event()

    def slow_cycle():
        entered.set()
        release.wait(timeout=2)
        return job._status(state="READY")

    monkeypatch.setattr(job, "_run_cycle_sync", slow_cycle)
    assert job.run_cycle()["state"] == "DISPATCHED"
    assert entered.wait(timeout=1)

    done = threading.Event()

    def stop_job():
        job.shutdown()
        done.set()

    stopper = threading.Thread(target=stop_job)
    stopper.start()
    assert not done.wait(timeout=0.05)

    release.set()
    stopper.join(timeout=1)
    assert done.is_set()
    assert job.last_status["state"] == "STOPPED"
    assert job.run_cycle()["state"] == "STOPPED"


def test_fast_watch_ticker_dispatches_independently(monkeypatch):
    pipeline = _Pipeline([])
    job = FastWatchRevisitJob(
        pipeline,
        interval_seconds=0.02,
    )

    dispatched = threading.Event()

    def dispatch():
        dispatched.set()
        return job._status(state="DISPATCHED")

    monkeypatch.setattr(job, "run_cycle", dispatch)

    assert job.start() is True
    assert job.start() is False
    assert dispatched.wait(timeout=1.0)

    result = job.shutdown()

    assert result["state"] == "STOPPED"
    assert job._ticker_thread is None


def test_runner_binds_fast_watch_to_independent_ticker():
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
    assert "fast_watch_revisit" not in jobs
    assert runner.fast_watch_revisit.pipeline is pipeline
    assert runner.fast_watch_revisit.interval_seconds == 20


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
