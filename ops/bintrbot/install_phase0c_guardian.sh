#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

mkdir -p "$ROOT/app" "$ROOT/state" "$ROOT/data/quality"

cat > "$ROOT/app/live_guardian.py" <<'PY'
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
    r = subprocess.run(
        ["systemctl", "is-active", "--quiet", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0

def stop_service(name: str):
    subprocess.run(
        ["systemctl", "stop", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

now = time.time()
nowms = now_ms()
free = shutil.disk_usage("/").free
free_gib = free / 1024**3

actions = []
alerts = []

collector_active = service_active("bintrbot-collector.service")
kline_active = service_active("bintrbot-backfill-klines.service")
agg_active = service_active("bintrbot-backfill-aggtrades.service")

# Preserve irreplaceable live data longer than refetchable historical backfills.
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

quality_age = None
if QUALITY.exists():
    quality_age = max(0.0, now - QUALITY.stat().st_mtime)

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

# Finalize only old raw files. Existing manifests are not silently overwritten.
created = 0
manifest_mismatch = []
for p in raw_files:
    st = p.stat()
    age = now - st.st_mtime
    mp = Path(str(p) + ".manifest.json")

    if mp.exists():
        try:
            m = json.loads(mp.read_text())
            if int(m.get("file_bytes", -1)) != st.st_size or int(m.get("file_mtime_ns", -1)) != st.st_mtime_ns:
                manifest_mismatch.append(str(p.relative_to(ROOT)))
        except Exception:
            manifest_mismatch.append(str(p.relative_to(ROOT)))
        continue

    if age < MANIFEST_MIN_AGE_SECONDS:
        continue

    info = {
        "schema_version": 1,
        "status": "SEALED",
        "source": "BINTRBOT_LIVE_RAW",
        "file": str(p.relative_to(ROOT)),
        "file_bytes": st.st_size,
        "file_mtime_ns": st.st_mtime_ns,
        "sha256": sha256(p),
        "sealed_at_ms": nowms,
        "sealed_at_utc": iso(nowms),
    }
    atomic_json(mp, info)
    created += 1

if manifest_mismatch:
    alerts.append("SEALED_RAW_FILE_CHANGED")

state = {
    "schema_version": 1,
    "checked_at_ms": nowms,
    "checked_at_utc": iso(nowms),
    "collector_active": service_active("bintrbot-collector.service"),
    "kline_backfill_active": service_active("bintrbot-backfill-klines.service"),
    "aggtrade_backfill_active": service_active("bintrbot-backfill-aggtrades.service"),
    "data_fresh": data_fresh,
    "stale_threshold_seconds": STALE_SECONDS,
    "quality_file_age_seconds": round(quality_age, 3) if quality_age is not None else None,
    "newest_raw_file": str(newest_raw.relative_to(ROOT)) if newest_raw else None,
    "newest_raw_age_seconds": round(newest_raw_age, 3) if newest_raw_age is not None else None,
    "raw_zst_files": len(raw_files),
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

cat > /etc/systemd/system/bintrbot-live-guardian.service <<'UNIT'
[Unit]
Description=BintrBot Live Data Guardian
After=local-fs.target

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/live_guardian.py
User=root
Nice=15
IOSchedulingClass=best-effort
IOSchedulingPriority=7
UNIT

cat > /etc/systemd/system/bintrbot-live-guardian.timer <<'UNIT'
[Unit]
Description=Run BintrBot Live Data Guardian Every Minute

[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=10s
Persistent=true
Unit=bintrbot-live-guardian.service

[Install]
WantedBy=timers.target
UNIT

cat > "$ROOT/phase0c-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== GUARDIAN =========='
cat /root/bintrbot/data/quality/guardian.json 2>/dev/null || echo 'guardian state missing'
echo
echo '========== LIVE QUALITY =========='
cat /root/bintrbot/data/quality/live.json 2>/dev/null || echo 'live quality missing'
echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-aggtrades.service || true
systemctl is-active bintrbot-live-guardian.timer || true
echo
echo '========== RAW =========='
du -sh /root/bintrbot/data/raw 2>/dev/null || true
printf 'RAW_ZST='
find /root/bintrbot/data/raw -type f -name '*.zst' 2>/dev/null | wc -l
printf 'SEALED_MANIFESTS='
find /root/bintrbot/data/raw -type f -name '*.manifest.json' 2>/dev/null | wc -l
echo
echo '========== SEQUENCE / RESYNC CODE EVIDENCE =========='
grep -nE 'lastUpdateId|sequence|gap|resync|snapshot|\["U"\]|\["u"\]|\.get\("U"\)|\.get\("u"\)'   /root/bintrbot/app/collector.py 2>/dev/null | head -n 120 || true
echo
echo '========== DISK =========='
df -h /
SH

chmod +x "$ROOT/phase0c-status.sh"

systemctl daemon-reload
systemctl enable --now bintrbot-live-guardian.timer

"$PY" "$ROOT/app/live_guardian.py"
echo
"$ROOT/phase0c-status.sh"
