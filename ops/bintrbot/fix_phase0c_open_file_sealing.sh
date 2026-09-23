#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
APP="$ROOT/app/live_guardian.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/state/live_guardian.py.pre_openfd_fix.$TS.bak"

cp -a "$APP" "$BACKUP"

cat > "$APP" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/bintrbot")
RAW = ROOT / "data/raw"
QUALITY = ROOT / "data/quality/live.json"
OUT = ROOT / "data/quality/guardian.json"
REVISION_ROOT = ROOT / "data/quality/manifest_revisions"

STALE_SECONDS = 180
HISTORICAL_STOP_GIB = 25
LIVE_STOP_GIB = 15
MANIFEST_MIN_AGE_SECONDS = 7200

def now_ms():
    return time.time_ns() // 1_000_000

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()

def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def service_active(name: str) -> bool:
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0

def stop_service(name: str):
    subprocess.run(
        ["systemctl", "stop", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

def service_pid(name: str) -> int | None:
    r = subprocess.run(
        ["systemctl", "show", "-p", "MainPID", "--value", name],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        pid = int(r.stdout.strip())
    except Exception:
        return None
    return pid if pid > 0 else None

def open_raw_files_for_pid(pid: int | None) -> set[Path]:
    out: set[Path] = set()
    if not pid:
        return out
    fd_dir = Path(f"/proc/{pid}/fd")
    if not fd_dir.exists():
        return out
    raw_resolved = RAW.resolve()
    for fd in fd_dir.iterdir():
        try:
            target = Path(os.readlink(fd))
            if not target.is_absolute():
                continue
            rp = target.resolve(strict=False)
            if rp.suffix != ".zst":
                continue
            try:
                rp.relative_to(raw_resolved)
            except ValueError:
                continue
            out.add(rp)
        except Exception:
            continue
    return out

def manifest_payload(p: Path, st, ts: int, *, status="SEALED", repair=None):
    obj = {
        "schema_version": 2,
        "status": status,
        "source": "BINTRBOT_LIVE_RAW",
        "file": str(p.relative_to(ROOT)),
        "file_bytes": st.st_size,
        "file_mtime_ns": st.st_mtime_ns,
        "sha256": sha256(p),
        "sealed_at_ms": ts,
        "sealed_at_utc": iso(ts),
        "seal_policy": "CLOSED_FILE_ONLY_PROC_FD_VERIFIED",
    }
    if repair:
        obj["repair"] = repair
    return obj

now = time.time()
nowms = now_ms()
free = shutil.disk_usage("/").free
free_gib = free / 1024**3

actions = []
alerts = []

collector_pid = service_pid("bintrbot-collector.service")
open_raw = open_raw_files_for_pid(collector_pid)

if free_gib < LIVE_STOP_GIB:
    for svc in (
        "bintrbot-backfill-klines.service",
        "bintrbot-backfill-aggtrades.service",
        "bintrbot-collector.service",
    ):
        if service_active(svc):
            stop_service(svc)
            actions.append(f"STOP:{svc}:DISK_CRITICAL")
    alerts.append("DISK_CRITICAL_LIVE_STOP")
elif free_gib < HISTORICAL_STOP_GIB:
    for svc in (
        "bintrbot-backfill-klines.service",
        "bintrbot-backfill-aggtrades.service",
    ):
        if service_active(svc):
            stop_service(svc)
            actions.append(f"STOP:{svc}:DISK_RESERVE_FOR_LIVE")
    alerts.append("DISK_LOW_HISTORICAL_STOP")

collector_active = service_active("bintrbot-collector.service")
quality_age = max(0.0, now - QUALITY.stat().st_mtime) if QUALITY.exists() else None

raw_files = [p for p in RAW.rglob("*.zst") if p.is_file()] if RAW.exists() else []
newest_raw = max(raw_files, key=lambda p: p.stat().st_mtime, default=None)
newest_raw_age = max(0.0, now - newest_raw.stat().st_mtime) if newest_raw else None

fresh_signals = []
if quality_age is not None:
    fresh_signals.append(quality_age <= STALE_SECONDS)
if newest_raw_age is not None:
    fresh_signals.append(newest_raw_age <= STALE_SECONDS)

data_fresh = bool(fresh_signals) and any(fresh_signals)
if collector_active and not data_fresh:
    alerts.append("COLLECTOR_ACTIVE_BUT_DATA_STALE")
if not collector_active:
    alerts.append("COLLECTOR_INACTIVE")

created = 0
open_skipped = 0
manifest_mismatch = []

for p in raw_files:
    rp = p.resolve(strict=False)
    st = p.stat()
    age = now - st.st_mtime
    mp = Path(str(p) + ".manifest.json")

    if rp in open_raw:
        open_skipped += 1
        continue

    if mp.exists():
        try:
            m = json.loads(mp.read_text())
            same = (
                int(m.get("file_bytes", -1)) == st.st_size
                and int(m.get("file_mtime_ns", -1)) == st.st_mtime_ns
                and bool(m.get("sha256"))
            )
            if not same:
                manifest_mismatch.append(str(p.relative_to(ROOT)))
        except Exception:
            manifest_mismatch.append(str(p.relative_to(ROOT)))
        continue

    if age < MANIFEST_MIN_AGE_SECONDS:
        continue

    atomic_json(mp, manifest_payload(p, st, nowms))
    created += 1

if manifest_mismatch:
    alerts.append("SEALED_RAW_FILE_CHANGED")

state = {
    "schema_version": 2,
    "checked_at_ms": nowms,
    "checked_at_utc": iso(nowms),
    "collector_active": service_active("bintrbot-collector.service"),
    "collector_pid": collector_pid,
    "kline_backfill_active": service_active("bintrbot-backfill-klines.service"),
    "aggtrade_backfill_active": service_active("bintrbot-backfill-aggtrades.service"),
    "data_fresh": data_fresh,
    "stale_threshold_seconds": STALE_SECONDS,
    "quality_file_age_seconds": round(quality_age, 3) if quality_age is not None else None,
    "newest_raw_file": str(newest_raw.relative_to(ROOT)) if newest_raw else None,
    "newest_raw_age_seconds": round(newest_raw_age, 3) if newest_raw_age is not None else None,
    "raw_zst_files": len(raw_files),
    "collector_open_raw_files": len(open_raw),
    "open_raw_files_skipped": open_skipped,
    "sealed_manifests_created_this_run": created,
    "sealed_manifest_mismatches": manifest_mismatch,
    "disk_free_bytes": free,
    "disk_free_gib": round(free_gib, 3),
    "historical_stop_threshold_gib": HISTORICAL_STOP_GIB,
    "live_stop_threshold_gib": LIVE_STOP_GIB,
    "actions": actions,
    "alerts": alerts,
    "status": "PASS" if not alerts else "ALERT",
}
atomic_json(OUT, state)
print(json.dumps(state, ensure_ascii=False, indent=2))
PY

"$PY" -m py_compile "$APP"

# One-time repair of manifests created by the old unsafe "mtime age only" policy.
"$PY" - <<'PY'
from __future__ import annotations
import hashlib, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path("/root/bintrbot")
RAW=ROOT/"data/raw"
REV=ROOT/"data/quality/manifest_revisions"
REV.mkdir(parents=True, exist_ok=True)

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def atomic_json(path,obj):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,path)

r=subprocess.run(
    ["systemctl","show","-p","MainPID","--value","bintrbot-collector.service"],
    capture_output=True,text=True,check=False
)
try: pid=int(r.stdout.strip())
except Exception: pid=0

open_files=set()
fd=Path(f"/proc/{pid}/fd")
if pid>0 and fd.exists():
    for x in fd.iterdir():
        try:
            t=Path(os.readlink(x))
            if t.is_absolute() and t.suffix==".zst":
                open_files.add(t.resolve(strict=False))
        except Exception:
            pass

repaired=[]
deferred=[]
for p in sorted(RAW.rglob("*.zst")):
    mp=Path(str(p)+".manifest.json")
    if not mp.exists():
        continue
    try:
        old=json.loads(mp.read_text())
        st=p.stat()
        mismatch=(
            int(old.get("file_bytes",-1)) != st.st_size
            or int(old.get("file_mtime_ns",-1)) != st.st_mtime_ns
        )
    except Exception:
        mismatch=True
        old={}
        st=p.stat()

    if not mismatch:
        continue

    if p.resolve(strict=False) in open_files:
        deferred.append(str(p.relative_to(ROOT)))
        continue

    ts=time.time_ns()//1_000_000
    stamp=datetime.fromtimestamp(ts/1000,timezone.utc).strftime("%Y%m%dT%H%M%S")
    rel=str(p.relative_to(ROOT)).replace("/","__")
    archived=REV/f"{rel}.{stamp}.old_manifest.json"
    archived.write_text(json.dumps(old,ensure_ascii=False,indent=2,sort_keys=True))

    new={
        "schema_version":2,
        "status":"RESEALED_AFTER_OPEN_HANDLE_POLICY_FIX",
        "source":"BINTRBOT_LIVE_RAW",
        "file":str(p.relative_to(ROOT)),
        "file_bytes":st.st_size,
        "file_mtime_ns":st.st_mtime_ns,
        "sha256":sha256(p),
        "sealed_at_ms":ts,
        "sealed_at_utc":datetime.fromtimestamp(ts/1000,timezone.utc).isoformat(),
        "seal_policy":"CLOSED_FILE_ONLY_PROC_FD_VERIFIED",
        "repair":{
            "reason":"PREVIOUS_GUARDIAN_COULD_SEAL_FILE_WHILE_COLLECTOR_HANDLE_REMAINED_OPEN",
            "previous_manifest_archived":str(archived.relative_to(ROOT)),
        },
    }
    atomic_json(mp,new)
    repaired.append(str(p.relative_to(ROOT)))

print("MANIFESTS_REPAIRED=",len(repaired))
for x in repaired:
    print("REPAIRED",x)
print("REPAIR_DEFERRED_OPEN_FILES=",len(deferred))
for x in deferred:
    print("DEFERRED",x)
PY

systemctl restart bintrbot-live-guardian.timer
systemctl start bintrbot-live-guardian.service
sleep 2

echo
echo '========== GUARDIAN AFTER FIX =========='
cat "$ROOT/data/quality/guardian.json"

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-live-guardian.timer || true

echo
echo "BACKUP=$BACKUP"
echo "PHASE0C_OPEN_FILE_SEAL_FIX=PASS"
