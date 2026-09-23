#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/test_phase0c_ws_reconnect.py" <<'PY'
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

COLLECTOR = Path("/root/bintrbot/app/collector.py")

spec = importlib.util.spec_from_file_location("bintrbot_live_collector_reconnect", COLLECTOR)
if spec is None or spec.loader is None:
    raise SystemExit("IMPORT_SPEC_FAILED")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

target_cls = None
for _, obj in inspect.getmembers(mod, inspect.isclass):
    if "ws_group" in obj.__dict__:
        target_cls = obj
        break
if target_cls is None:
    raise SystemExit("COLLECTOR_CLASS_NOT_FOUND")

class FakeWS:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []
    async def send(self, data):
        self.sent.append(json.loads(data))
    def __aiter__(self):
        self._it = iter(self.messages)
        return self
    async def __anext__(self):
        try:
            item = next(self._it)
        except StopIteration:
            raise StopAsyncIteration
        if isinstance(item, BaseException):
            raise item
        return item

class FakeConnect:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
    def __call__(self, *args, **kwargs):
        parent = self
        class CM:
            async def __aenter__(self_inner):
                idx = parent.calls
                parent.calls += 1
                outcome = parent.outcomes[idx]
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome
            async def __aexit__(self_inner, exc_type, exc, tb):
                return False
        return CM()

def check(cond, name):
    if not cond:
        raise AssertionError(name)
    print("PASS", name)

async def main():
    obj = target_cls.__new__(target_cls)
    obj.stop = asyncio.Event()
    obj.ws_reconnects = 0
    obj.ws_reconnect_events = 0
    obj.ws_disconnects = 0
    obj.ws_parse_errors = 0
    obj.ws_unknown_symbols = 0
    obj.ws_unknown_events = 0

    async def on_depth(info, payload):
        obj.stop.set()
    async def on_trade(info, payload):
        obj.stop.set()

    obj.on_depth = on_depth
    obj.on_trade = on_trade

    info = SimpleNamespace(
        api_symbol="TESTTRY",
        stream_symbol="testtry",
        symbol_type=1,
    )

    second = FakeWS([
        json.dumps({"e":"depthUpdate","s":"TESTTRY","U":1,"u":1})
    ])
    fake = FakeConnect([
        RuntimeError("forced_first_connect_failure"),
        second,
    ])

    original_connect = mod.websockets.connect
    original_sleep = mod.asyncio.sleep

    async def fast_sleep(_):
        return None

    mod.websockets.connect = fake
    mod.asyncio.sleep = fast_sleep
    try:
        await asyncio.wait_for(
            obj.ws_group([info], "offline-reconnect-test"),
            timeout=2,
        )
    finally:
        mod.websockets.connect = original_connect
        mod.asyncio.sleep = original_sleep

    check(fake.calls >= 2, "ws_connect_retried")
    check(obj.ws_disconnects >= 1, "ws_disconnect_counted")
    check(obj.ws_reconnects >= 1, "ws_successful_connection_counted")
    check(len(second.sent) >= 1, "subscriptions_resent_after_reconnect")
    check(obj.stop.is_set(), "post_reconnect_event_processed")

    print()
    print("PHASE0C_WS_RECONNECT_TEST=PASS")
    print("NETWORK_USED=false")
    print("LIVE_SERVICE_TOUCHED=false")
    print("COLLECTOR_FILE_MODIFIED=false")
    print("CONNECT_ATTEMPTS=", fake.calls)
    print("WS_DISCONNECTS=", obj.ws_disconnects)
    print("WS_CONNECTIONS_TOTAL=", obj.ws_reconnects)

asyncio.run(main())
PY

echo '========== OFFLINE WS RECONNECT =========='
"$PY" "$ROOT/app/test_phase0c_ws_reconnect.py"

echo
echo '========== LIVE HEALTH UNTOUCHED =========='
cat "$ROOT/data/quality/live.json"

echo
echo '========== GUARDIAN =========='
cat "$ROOT/data/quality/guardian.json"

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-live-guardian.timer || true
