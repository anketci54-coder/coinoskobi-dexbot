import threading
import time
from collections import OrderedDict
from types import SimpleNamespace

from app.dex.runtime_market_flow import RuntimeMarketFlowStore
from app.pipeline import tx_origin_readiness_gate as gate
from app.pipeline.engine import Pipeline


PAIR = "0x00000000000000000000000000000000000000aa"


def _runtime():
    runtime = RuntimeMarketFlowStore()
    runtime._events[PAIR] = OrderedDict(
        (
            (
                "bull",
                {
                    "direction": "BULL",
                    "transaction_hash": "0xbull",
                },
            ),
            (
                "bear",
                {
                    "direction": "BEAR",
                    "transaction_hash": "0xbear",
                },
            ),
        )
    )
    return runtime


def test_pipeline_class_installs_origin_readiness_gate():
    assert Pipeline._tx_origin_readiness_gate_installed is True
    assert (
        Pipeline.wait_for_native_market_evidence
        is gate.wait_for_native_market_evidence_with_origin
    )


def test_unresolved_origins_remain_fail_closed(monkeypatch):
    runtime = _runtime()
    pipeline = SimpleNamespace(native_market_flow=runtime)

    monkeypatch.setattr(
        gate,
        "resolved_transaction_origin",
        lambda _tx_hash: None,
    )

    result = gate.wait_for_native_market_evidence_with_origin(
        pipeline,
        [PAIR],
        timeout=0.0,
    )

    assert result["state"] == "TIMEOUT"
    assert result["ready"] == 0
    assert result["pending"] == 1
    assert result["identity_source"] == "TRANSACTION_FROM_ONLY"
    assert result["decision_authority"] is False
    assert result["execution_authority"] is False


def test_real_bull_and_bear_origins_make_pair_ready(monkeypatch):
    runtime = _runtime()
    pipeline = SimpleNamespace(native_market_flow=runtime)

    origins = {
        "0xbull": "0x0000000000000000000000000000000000000001",
        "0xbear": "0x0000000000000000000000000000000000000002",
    }

    monkeypatch.setattr(
        gate,
        "resolved_transaction_origin",
        origins.get,
    )

    result = gate.wait_for_native_market_evidence_with_origin(
        pipeline,
        [PAIR],
        timeout=0.0,
    )

    assert result["state"] == "READY"
    assert result["ready"] == 1
    assert result["pending"] == 0
    assert result["ready_pairs"] == [PAIR]
    assert result["swap_sender_is_wallet"] is False


def test_background_origin_resolution_can_mature_inside_bound(monkeypatch):
    runtime = _runtime()
    pipeline = SimpleNamespace(native_market_flow=runtime)
    origins = {}

    monkeypatch.setattr(
        gate,
        "resolved_transaction_origin",
        origins.get,
    )

    def resolve_later():
        time.sleep(0.03)
        origins.update(
            {
                "0xbull": "0x0000000000000000000000000000000000000001",
                "0xbear": "0x0000000000000000000000000000000000000002",
            }
        )

    worker = threading.Thread(target=resolve_later)
    worker.start()

    started = time.monotonic()
    result = gate.wait_for_native_market_evidence_with_origin(
        pipeline,
        [PAIR],
        timeout=0.20,
    )
    elapsed = time.monotonic() - started

    worker.join()

    assert result["state"] == "READY"
    assert result["ready"] == 1
    assert elapsed < 0.20
    assert result["bounded"] is True
