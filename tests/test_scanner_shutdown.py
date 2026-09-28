"""Cancellation must cover discovery and the broker's separate HTTP clients."""

import threading
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.market_data.broker import MarketDataBroker
from app.scanner.gecko_scanner import GeckoScanner
from app.universe.snapshot import (
    DexScreenerSnapshotClient,
    GeckoTerminalSnapshotClient,
    ProviderStickySnapshotClient,
)


@pytest.mark.parametrize("path", ["discovery", "legacy_multi", "legacy_dex", "primary", "fallback"])
def test_stop_releases_inflight_http_without_publishing_late_rows(monkeypatch, path):
    entered, release, finished = (threading.Event() for _ in range(3))
    calls, results, errors, persisted = [], [], [], []
    pool = "0x" + "1" * 40

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def close(self):
            finished.set()

        def json(self):
            return {"data": [{"attributes": {"address": pool, "base_token_price_usd": "1.25"}}], "pairs": []}

    def blocked_get(*args, **kwargs):
        calls.append(args[0])
        entered.set()
        assert release.wait(5)
        return Response()

    scanner = GeckoScanner()
    monkeypatch.setattr("app.scanner.gecko_scanner.requests.get", blocked_get)
    monkeypatch.setattr("app.scanner.gecko_scanner.persist_registered_followup_snapshots", persisted.append)
    monkeypatch.setattr("app.market_data.broker.persist_registered_followup_snapshots", persisted.append)
    stopper = scanner
    if path == "discovery":
        fetch = scanner.scan
    elif path == "legacy_multi":
        fetch = lambda: scanner.pool_snapshots([pool])
    elif path == "legacy_dex":
        monkeypatch.setattr(scanner, "_provider_available", lambda name: name == "dexscreener")
        fetch = lambda: scanner.pool_snapshots([pool])
    else:
        session = SimpleNamespace(get=blocked_get)
        client = ProviderStickySnapshotClient(
            primary=DexScreenerSnapshotClient(session=session),
            fallback=GeckoTerminalSnapshotClient(session=session),
        )
        stopper = MarketDataBroker(scanner, snapshot_client=client)
        identity = {"pool": pool, "dex": "pancakeswap_v2"}
        if path == "fallback":
            identity["latest_snapshot_source"] = "geckoterminal"
        fetch = lambda: stopper.pool_snapshots([identity], persist_followups=True)

    def consume():
        try:
            results.extend(fetch())
        except RuntimeError as exc:
            errors.append(str(exc))

    consumer = threading.Thread(target=consume)
    consumer.start()
    try:
        assert entered.wait(1)
        stopper.request_stop()
        consumer.join(0.5)
        assert not consumer.is_alive(), "HTTP wait ignored shutdown"
        assert not results and not persisted
        # A second call must neither start HTTP nor return cached/late facts.
        consume()
        assert len(calls) == 1
        assert not results and not persisted
    finally:
        release.set()
        consumer.join(2)
    assert finished.wait(1), "late HTTP response was not closed"
    assert not results and not persisted


@pytest.mark.parametrize("path", ["discovery", "snapshots"])
def test_runner_sigterm_during_http_exits_process(path, tmp_path):
    # The transport deliberately never returns. A ThreadPoolExecutor would
    # pass a caller-only timeout test but hang Python's interpreter exit.
    script = r'''
import os, signal, threading
from types import SimpleNamespace
from app.core.runner import Runner
from app.pipeline.engine import PipelineEngine
from app.pipeline.work_scheduler import WorkScheduler
from app.scanner.gecko_scanner import GeckoScanner
from app.market_data.broker import MarketDataBroker
from app.universe.snapshot import DexScreenerSnapshotClient, ProviderStickySnapshotClient
import app.scanner.gecko_scanner as gecko
import app.chains.bsc as bsc

def blocked_get(*a, **kw):
    os.kill(os.getpid(), signal.SIGTERM)
    threading.Event().wait()

gecko.requests.get = blocked_get
bsc.w3 = SimpleNamespace(provider=SimpleNamespace(request_stop=lambda: True))
pipeline = PipelineEngine.__new__(PipelineEngine)
pipeline.work_scheduler = WorkScheduler(max_workers=1)
pipeline.scanner = MarketDataBroker(GeckoScanner(), snapshot_client=ProviderStickySnapshotClient(
    primary=DexScreenerSnapshotClient(session=SimpleNamespace(get=blocked_get))))
pipeline.cache = SimpleNamespace(replace=lambda row: (_ for _ in ()).throw(AssertionError("late write")))

def scan():
    if PATH == "discovery":
        result = pipeline.run_cycle()
        assert result["state"] == "STOPPED"
    else:
        pipeline.scanner.pool_snapshots([{"pool": "0x" + "1" * 40, "dex": "pancakeswap_v2"}])

runner = Runner(scan_job=scan, auxiliary_service_factory=lambda: [])
runner.pipeline = pipeline
runner.run()
assert pipeline.work_scheduler.is_stopping()
assert pipeline.scanner.is_stopping()
assert not any(t.name == "coinoskobi-shutdown" for t in threading.enumerate())
print("clean exit with blocked HTTP")
'''
    result = subprocess.run(
        [sys.executable, "-c", "PATH = " + repr(path) + "\n" + script],
        capture_output=True, text=True, timeout=8,
    )
    assert result.returncode == 0, result.stderr
    assert "clean exit with blocked HTTP" in result.stdout


def test_transport_slots_and_waiters_are_bounded_and_cancelled():
    from app.market_data.http_reader import CancellableHTTPReader, HTTPReadCancelled

    reader = CancellableHTTPReader(max_inflight=1)
    entered, release, closed = (threading.Event() for _ in range(3))
    calls, errors = [], []

    def get(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return SimpleNamespace(close=closed.set)

    def consume():
        try:
            reader.get(get, "https://example.invalid")
        except HTTPReadCancelled:
            errors.append(1)

    callers = [threading.Thread(target=consume) for _ in range(8)]
    try:
        for caller in callers:
            caller.start()
        assert entered.wait(1)
        reader.request_stop()
        for caller in callers:
            caller.join(0.5)
        assert not any(caller.is_alive() for caller in callers)
        assert len(errors) == 8
        assert calls == [1]
    finally:
        release.set()
        for caller in callers:
            caller.join(2)
    assert closed.wait(1)


def test_buffered_http_preserves_payload_and_exception():
    from app.market_data.http_reader import CancellableHTTPReader
    import requests

    reader = CancellableHTTPReader()
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"data": [{"price_usd": 1.25}]}'
    response._content_consumed = True
    assert reader.get(lambda *a: response, "url").json() == {
        "data": [{"price_usd": 1.25}],
    }

    def fail(*args):
        raise requests.Timeout("provider timed out")

    with pytest.raises(requests.Timeout, match="provider timed out"):
        reader.get(fail, "url")


def test_scanner_drains_durable_observation_without_global_status_after_stop():
    from app.pipeline.engine import PipelineEngine
    from app.pipeline.work_scheduler import WorkScheduler
    from app.pipeline.candidate_queue import CandidateAdmissionQueue
    from test_pipeline_queue import FakeCache, candidate

    engine = PipelineEngine.__new__(PipelineEngine)
    row = candidate(1)
    row["observed_at"] = "2026-09-28T12:00:00+00:00"
    engine.cache = FakeCache([row])
    engine.filter = SimpleNamespace(filter_all=lambda rows: rows)
    engine.work_scheduler = WorkScheduler(max_workers=1)
    engine.candidate_queue = CandidateAdmissionQueue()
    writes = []

    def forbidden_status():
        pytest.fail("shutdown waited for an unused global diagnostic scan")

    engine.counterfactual_store = SimpleNamespace(
        observe=lambda **kw: {"state": "UNKNOWN"},
        record=lambda **kw: writes.append("record") or {"state": "RECORDED"},
        status=forbidden_status,
    )
    engine.watch_probe_store = SimpleNamespace(
        observe=lambda **kw: writes.append("observe") or {},
        open_probe=lambda **kw: writes.append("probe") or {"state": "EXISTS"},
    )
    engine.watch_probe_entry_snapshot_store = SimpleNamespace()

    def run(*a, **kw):
        engine.work_scheduler.request_stop()
        return {"success": True, "data": {"paper": {"action": "WATCH"}}}

    engine.run = run
    result = engine.run_cycle()
    assert result["state"] == "STOPPED"
    assert writes == ["observe", "record", "probe"]


def test_refresh_stops_between_history_reads_without_fetching_or_pruning():
    from app.pipeline.engine import PipelineEngine
    from app.pipeline.work_scheduler import WorkScheduler

    engine = PipelineEngine.__new__(PipelineEngine)
    engine.work_scheduler = WorkScheduler(max_workers=1)
    reads, fetched, pruned = [], [], []

    def history(pool, **kwargs):
        reads.append(pool)
        engine.work_scheduler.request_stop()
        return [{"pool": pool, "dex": "pancakeswap_v2"}]

    engine.cache = SimpleNamespace(all=lambda: [], history_for_pool=history,
                                   prune_except=lambda *a, **kw: pruned.append(1))
    engine.scanner = SimpleNamespace(scan=lambda: [],
                                     pool_prices=lambda pools: fetched.append(pools) or {})
    engine.counterfactual_store = SimpleNamespace(
        pending_pool_snapshot=lambda **kw: {f"token{i}": f"pool{i}" for i in range(30)},
        observe_durable=lambda **kw: {},
    )
    assert engine.run_cycle()["state"] == "STOPPED"
    assert len(reads) == 1
    assert not fetched and not pruned
