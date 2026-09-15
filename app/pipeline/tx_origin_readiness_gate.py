import time
from collections import OrderedDict

from app.dex.transaction_origin import resolved_transaction_origin


_POLL_SECONDS = 0.05


def _address(value):
    value = str(value or "").strip().lower()
    return value or None


def _origin_ready_pairs(runtime, requested):
    ready = []

    for pair in requested:
        events = runtime._events.get(
            pair,
            OrderedDict(),
        )

        bull_origins = {
            resolved_transaction_origin(
                row.get("transaction_hash")
            )
            for row in events.values()
            if row.get("direction") == "BULL"
        }
        bull_origins.discard(None)

        bear_origins = {
            resolved_transaction_origin(
                row.get("transaction_hash")
            )
            for row in events.values()
            if row.get("direction") == "BEAR"
        }
        bear_origins.discard(None)

        if bull_origins and bear_origins:
            ready.append(pair)

    return ready


def wait_for_native_market_evidence_with_origin(
    self,
    pairs,
    *,
    timeout=10.0,
):
    runtime = getattr(
        self,
        "native_market_flow",
        None,
    )

    if runtime is None:
        return {
            "state": "UNAVAILABLE",
            "requested": 0,
            "ready": 0,
            "pending": 0,
            "decision_authority": False,
            "execution_authority": False,
        }

    if isinstance(pairs, str):
        requested = [_address(pairs)]
    else:
        requested = [
            _address(pair)
            for pair in (pairs or [])
        ]

    requested = [
        pair
        for pair in dict.fromkeys(requested)
        if pair
    ]

    timeout = max(0.0, float(timeout))

    if not requested:
        return {
            "state": "NO_TARGETS",
            "requested": 0,
            "ready": 0,
            "pending": 0,
            "ready_pairs": [],
            "timeout": timeout,
            "identity_source": "TRANSACTION_FROM_ONLY",
            "decision_authority": False,
            "execution_authority": False,
        }

    condition = getattr(
        runtime,
        "_event_condition",
        None,
    )
    stop_event = getattr(
        runtime,
        "_stop_event",
        None,
    )

    if condition is None or stop_event is None:
        return {
            "state": "UNAVAILABLE",
            "requested": len(requested),
            "ready": 0,
            "pending": len(requested),
            "ready_pairs": [],
            "timeout": timeout,
            "identity_source": "TRANSACTION_FROM_ONLY",
            "decision_authority": False,
            "execution_authority": False,
        }

    deadline = time.monotonic() + timeout

    with condition:
        while True:
            ready = _origin_ready_pairs(
                runtime,
                requested,
            )

            if stop_event.is_set():
                state = "STOPPED"
                break

            if len(ready) == len(requested):
                state = "READY"
                break

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                state = "PARTIAL" if ready else "TIMEOUT"
                break

            condition.wait(
                timeout=min(
                    remaining,
                    _POLL_SECONDS,
                )
            )

    return {
        "state": state,
        "requested": len(requested),
        "ready": len(ready),
        "pending": len(requested) - len(ready),
        "ready_pairs": list(ready),
        "timeout": timeout,
        "identity_source": "TRANSACTION_FROM_ONLY",
        "swap_sender_is_wallet": False,
        "bounded": True,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def install_pipeline_tx_origin_readiness_gate(pipeline_class):
    if getattr(
        pipeline_class,
        "_tx_origin_readiness_gate_installed",
        False,
    ):
        return False

    pipeline_class._tx_origin_readiness_original_waiter = (
        pipeline_class.wait_for_native_market_evidence
    )
    pipeline_class.wait_for_native_market_evidence = (
        wait_for_native_market_evidence_with_origin
    )
    pipeline_class._tx_origin_readiness_gate_installed = True
    return True
