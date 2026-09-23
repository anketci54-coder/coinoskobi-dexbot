#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/test_phase0c_sequence_recovery.py" <<'PY'
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import sys
from collections import deque
from pathlib import Path
from types import SimpleNamespace

COLLECTOR = Path("/root/bintrbot/app/collector.py")

spec = importlib.util.spec_from_file_location("bintrbot_live_collector", COLLECTOR)
if spec is None or spec.loader is None:
    raise SystemExit("IMPORT_SPEC_FAILED")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

target_cls = None
for _, obj in inspect.getmembers(mod, inspect.isclass):
    if "sync_from_snapshot" in obj.__dict__ and "on_depth" in obj.__dict__:
        target_cls = obj
        break

if target_cls is None:
    raise SystemExit("COLLECTOR_CLASS_NOT_FOUND")

class DummyWriter:
    def __init__(self):
        self.items = []
    async def put(self, item):
        self.items.append(item)

def state(*, synced=False, last_u=None, buffer=None, gaps=0):
    return SimpleNamespace(
        synced=synced,
        last_u=last_u,
        buffer=deque(buffer or [], maxlen=50000),
        gaps=gaps,
        snapshot_id=None,
        snapshot_queued=False,
    )

def make_obj(st):
    obj = target_cls.__new__(target_cls)
    obj.books = {"TESTTRY": st}
    obj.snapshot_q = asyncio.Queue()
    obj.writer = DummyWriter()
    obj.depth_events = 0
    return obj

def check(cond, name):
    if not cond:
        raise AssertionError(name)
    print("PASS", name)

# 1) Snapshot with no buffered events.
s = state()
o = make_obj(s)
o.sync_from_snapshot("TESTTRY", 100)
check(s.synced is True, "snapshot_empty_sets_synced")
check(s.last_u == 100, "snapshot_empty_sets_last_u")

# 2) Snapshot bridges into contiguous buffered diff events.
s = state(buffer=[
    {"U": 101, "u": 101},
    {"U": 102, "u": 102},
    {"U": 103, "u": 103},
])
o = make_obj(s)
o.sync_from_snapshot("TESTTRY", 100)
check(s.synced is True, "snapshot_contiguous_buffer_synced")
check(s.last_u == 103, "snapshot_contiguous_buffer_advances_last_u")
check(len(s.buffer) == 0, "snapshot_contiguous_buffer_cleared")

# 3) Inject a deterministic hole inside buffered events.
s = state(buffer=[
    {"U": 101, "u": 101},
    {"U": 103, "u": 103},
])
o = make_obj(s)
o.sync_from_snapshot("TESTTRY", 100)
check(s.synced is False, "snapshot_internal_gap_unsynced")
check(s.gaps == 1, "snapshot_internal_gap_counted")
check(len(s.buffer) >= 1, "snapshot_internal_gap_retained")

# 4) Live stream gap must mark unsynced and request a new snapshot.
async def live_gap_case():
    s = state(synced=True, last_u=200)
    o = make_obj(s)
    info = SimpleNamespace(
        api_symbol="TESTTRY",
        symbol="TEST_TRY",
        symbol_type=1,
        base_asset="TEST",
        quote_asset="TRY",
    )
    payload = {"U": 202, "u": 202, "E": 1}
    await o.on_depth(info, payload)
    check(s.synced is False, "live_gap_unsynced")
    check(s.gaps == 1, "live_gap_counted")
    check(s.snapshot_queued is True, "live_gap_snapshot_flag_set")
    check(o.snapshot_q.qsize() == 1, "live_gap_snapshot_enqueued")
    check(len(o.writer.items) == 1, "live_gap_written")
    quality = o.writer.items[0].get("quality")
    check(quality == "GAP", "live_gap_quality_GAP")

asyncio.run(live_gap_case())

print()
print("PHASE0C_SEQUENCE_INJECTION=PASS")
print("NETWORK_USED=false")
print("LIVE_SERVICE_TOUCHED=false")
print("COLLECTOR_FILE_MODIFIED=false")
print("COLLECTOR_CLASS=" + target_cls.__name__)
PY

echo '========== OFFLINE SEQUENCE INJECTION =========='
"$PY" "$ROOT/app/test_phase0c_sequence_recovery.py"

echo
echo '========== SNAPSHOT WORKER RECOVERY PATH =========='
nl -ba "$ROOT/app/collector.py" | sed -n '310,376p'

echo
echo '========== LIVE SERVICES AFTER TEST =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-live-guardian.timer || true
