#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
APP="$ROOT/app/backfill_aggtrades.py"
UNIT="/etc/systemd/system/bintrbot-backfill-aggtrades.service"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

if [ ! -f "$APP" ]; then
  echo "AGGTRADES_APP_MISSING=$APP"
  exit 2
fi

mkdir -p "$ROOT/state" /etc/systemd/system/bintrbot-backfill-aggtrades.service.d

cp -a "$APP" "$ROOT/state/backfill_aggtrades.py.pre_low_impact.$TS.bak"
[ -f "$UNIT" ] && cp -a "$UNIT" "$ROOT/state/bintrbot-backfill-aggtrades.service.pre_low_impact.$TS.bak"

"$PY" - "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()

pairs=[
    ("MIN_FREE = 20 * 1024**3","MIN_FREE = 35 * 1024**3"),
    ("REQ_GAP = 1.0","REQ_GAP = 2.0"),
]
for old,new in pairs:
    if old in s:
        s=s.replace(old,new,1)
    elif new not in s:
        raise SystemExit(f"PATCH_ABORT missing: {old}")

p.write_text(s)
print("AGGTRADES_LOW_IMPACT_PATCH=YES")
PY

cat > /etc/systemd/system/bintrbot-backfill-aggtrades.service.d/20-low-impact.conf <<'UNIT'
[Service]
Nice=19
IOSchedulingClass=idle
CPUQuota=35%
UNIT

cat > "$ROOT/app/aggtrades_guardian.py" <<'PY'
from __future__ import annotations
import json, os, shutil, subprocess, time
from pathlib import Path

ROOT=Path("/root/bintrbot")
OUT=ROOT/"state/aggtrades_guardian.json"
GUARD=ROOT/"data/quality/guardian.json"
KLINES=ROOT/"state/backfill_klines.json"
MIN_FREE=35*1024**3

def load(p):
    try:return json.loads(p.read_text())
    except Exception:return {}

def active(unit):
    return subprocess.run(
        ["systemctl","is-active","--quiet",unit],
        check=False
    ).returncode==0

def atomic(p,obj):
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(t,p)

reasons=[]
free=shutil.disk_usage("/").free
g=load(GUARD)
k=load(KLINES)

if free < MIN_FREE:
    reasons.append("DISK_BELOW_35_GIB")
if not active("bintrbot-collector.service"):
    reasons.append("COLLECTOR_NOT_ACTIVE")
if g and (g.get("status")!="PASS" or g.get("data_fresh") is not True):
    reasons.append("LIVE_GUARDIAN_NOT_HEALTHY")
errors=k.get("errors") or {}
if isinstance(errors,(dict,list)) and len(errors)>0:
    reasons.append("MAIN_KLINE_BACKFILL_ERRORS")

agg_active=active("bintrbot-backfill-aggtrades.service")
action="NONE"
if reasons and agg_active:
    subprocess.run(["systemctl","stop","bintrbot-backfill-aggtrades.service"],check=False)
    action="AGGTRADES_STOPPED_FAIL_SAFE"

out={
    "schema_version":1,
    "checked_at_ms":time.time_ns()//1_000_000,
    "status":"PASS" if not reasons else "STOPPED_OR_BLOCKED",
    "reasons":reasons,
    "action":action,
    "free_gib":round(free/1024**3,2),
    "collector_active":active("bintrbot-collector.service"),
    "aggtrades_active_after_check":active("bintrbot-backfill-aggtrades.service"),
    "live_guardian_status":g.get("status"),
    "live_data_fresh":g.get("data_fresh"),
    "main_kline_status":k.get("status"),
    "main_kline_jobs_remaining":k.get("jobs_remaining"),
}
atomic(OUT,out)
print(json.dumps(out,ensure_ascii=False,indent=2))
PY

cat > /etc/systemd/system/bintrbot-aggtrades-guardian.service <<'UNIT'
[Unit]
Description=BintrBot aggTrades safety guardian

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/aggtrades_guardian.py
User=root
Nice=19
IOSchedulingClass=idle
UNIT

cat > /etc/systemd/system/bintrbot-aggtrades-guardian.timer <<'UNIT'
[Unit]
Description=Check aggTrades backfill safety every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=true
Unit=bintrbot-aggtrades-guardian.service

[Install]
WantedBy=timers.target
UNIT

cat > "$ROOT/aggtrades-safe-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== AGGTRADES =========='
systemctl is-active bintrbot-backfill-aggtrades.service || true
python3 - <<'PY'
import json
from pathlib import Path
for f in [
 "/root/bintrbot/state/backfill_aggtrades.json",
 "/root/bintrbot/state/aggtrades_guardian.json"
]:
    p=Path(f)
    print("\n---",p.name,"---")
    if not p.exists():
        print("not ready"); continue
    x=json.loads(p.read_text())
    for k in [
      "status","symbols_total","rows_total","parts_total","errors",
      "free_gib","reasons","action","main_kline_jobs_remaining"
    ]:
        if k in x:
            v=x[k]
            if k=="errors" and isinstance(v,(dict,list)):
                v=len(v)
            print(k.upper(),"=",v)
PY
echo
echo '========== CORE =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
echo
echo '========== DISK =========='
df -h /
echo
echo '========== RECENT LOG =========='
journalctl -u bintrbot-backfill-aggtrades.service -n 20 --no-pager || true
SH
chmod +x "$ROOT/aggtrades-safe-status.sh"

"$PY" -m py_compile "$APP" "$ROOT/app/aggtrades_guardian.py"

systemctl daemon-reload
systemctl enable --now bintrbot-aggtrades-guardian.timer

# Pre-flight guardian must pass before start.
"$PY" "$ROOT/app/aggtrades_guardian.py"

STATUS="$("$PY" - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/state/aggtrades_guardian.json")
x=json.loads(p.read_text()) if p.exists() else {}
print(x.get("status","UNKNOWN"))
PY
)"

if [ "$STATUS" != "PASS" ]; then
  echo "AGGTRADES_START_BLOCKED_BY_GUARDIAN=$STATUS"
  "$ROOT/aggtrades-safe-status.sh"
  exit 3
fi

systemctl start bintrbot-backfill-aggtrades.service
sleep 12

"$PY" "$ROOT/app/aggtrades_guardian.py"
echo
"$ROOT/aggtrades-safe-status.sh"

echo
echo "AGGTRADES_LOW_IMPACT_START=PASS"
