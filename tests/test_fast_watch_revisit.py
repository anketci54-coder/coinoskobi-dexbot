import json

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


class _Cache:
    def all(self):
        return [{
            "pool": POOL,
            "token": f"bsc_{TOKEN}",
            "quote_token": QUOTE,
        }]


class _Flow:
    def __init__(self):
        self.confirmed = []

    def confirm_pair_membership(self, pool, token, quote):
        self.confirmed.append((pool, token, quote))
        return {"state": "VERIFIED"}


class _Pipeline:
    def __init__(self, rows):
        self.counterfactual_store = _Store(rows)
        self.cache = _Cache()
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


def _history_row(reason, *, hard_block=False, token=TOKEN, pool=POOL):
    return {
        "token": token,
        "pool": pool,
        "decision_action": "WATCH",
        "context_json": json.dumps({
            "strategy": "PAPER_BUY",
            "opportunity_state": "WATCH",
            "opportunity_reason": reason,
            "hard_block": hard_block,
        }),
    }


def test_fast_watch_selects_only_active_momentum_reasons(monkeypatch):
    rows = [
        _history_row("ACTIVE_MOMENTUM_NOT_POSITIVE"),
        _history_row("QUOTE_FLOW_NOT_SUPPORTING_MOVE", token="0x03", pool="0x04"),
        _history_row("POSITIVE_CONTINUATION_NOT_ESTABLISHED", hard_block=True, token="0x05", pool="0x06"),
    ]
    pipeline = _Pipeline(rows)

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

    job = FastWatchRevisitJob(
        pipeline,
        max_candidates=30,
    )
    result = job.run_cycle()

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
    job = FastWatchRevisitJob(
        pipeline,
        max_candidates=30,
    )

    identities = job._watched_identities()
    assert len(identities) == 30
    assert len(set(identities)) == 30
    assert job._status(state="READY")["max_candidates"] == 30


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
