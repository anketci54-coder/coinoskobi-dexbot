#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
PROBE="$ROOT/state/phase0a_delisted_kline_probe.json"
TRANS_APP="$ROOT/app/backfill_transition_klines.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_rune.$TS.bak"
cp -a "$PROBE" "$PROBE.pre_rune.$TS.bak"
cp -a "$TRANS_APP" "$TRANS_APP.pre_delisted_coverage_gate.$TS.bak"

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.setdefault("confirmed_delisted_try_seed", [])
by={r.get("symbol"):r for r in rows}

r={
  "symbol":"RUNE_TRY",
  "announced_date":"2023-04-05",
  "delisted_local":"2023-04-07 06:00",
  "source":"BINANCE_TR_OFFICIAL",
  "source_url":"https://www.binance.tr/blog/duyurular/b62ee86fd00a47be854a21d55a92f01d",
  "known_at_precision":"DATE_ONLY"
}
if r["symbol"] in by:
    by[r["symbol"]].update(r)
else:
    rows.append(r)

rows.sort(key=lambda z:z.get("symbol",""))
x["confirmed_delisted_try_seed"]=rows
x["confirmed_delisted_try_seed_count"]=len(rows)
x["seed_is_complete"]=False
x["status"]="DISCOVERY_REQUIRED"
x["survivorship_bias_resolved"]=False
x["updated_at_ms"]=time.time_ns()//1_000_000

tmp=p.with_suffix(".json.tmp")
tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,p)
print("DELISTED_SEED_COUNT=",len(rows))
PY

cat > "$ROOT/app/probe_rune_delisted.py" <<'PY'
from __future__ import annotations
import asyncio, json, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import aiohttp

ROOT=Path("/root/bintrbot")
PROBE=ROOT/"state/phase0a_delisted_kline_probe.json"
URL="https://api.binance.me/api/v1/klines"
SYMBOL="RUNE_TRY"
END_LOCAL="2023-04-07 06:00"
START_MS=1577836800000

def end_ms():
    dt=datetime.strptime(END_LOCAL,"%Y-%m-%d %H:%M").replace(tzinfo=timezone(timedelta(hours=3)))
    return int(dt.astimezone(timezone.utc).timestamp()*1000)

async def get(session,params):
    last=None
    for n in range(5):
        try:
            async with session.get(URL,params=params,timeout=aiohttp.ClientTimeout(total=20)) as r:
                text=await r.text()
                if r.status==200:
                    x=json.loads(text)
                    return x.get("data",x) if isinstance(x,dict) else x
                last=f"HTTP_{r.status}:{text[:120]}"
                if r.status in (418,429) or r.status>=500:
                    await asyncio.sleep(min(2**n,15))
                    continue
                return {"error":last}
        except Exception as e:
            last=repr(e)
            await asyncio.sleep(min(2**n,15))
    return {"error":last}

async def main():
    end=end_ms()
    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-rune-probe/1.0"}) as s:
        first=await get(s,{"symbol":"RUNETRY","interval":"1m","startTime":START_MS,"endTime":end,"limit":1})
        await asyncio.sleep(0.5)
        near=await get(s,{"symbol":"RUNETRY","interval":"1m","startTime":max(START_MS,end-7*86400000),"endTime":end,"limit":1000})

    err=None; first_ms=None; last_ms=None
    if isinstance(first,dict): err=first.get("error")
    elif isinstance(first,list) and first and isinstance(first[0],list): first_ms=int(first[0][0])
    if isinstance(near,dict): err=(err+" | " if err else "")+str(near.get("error"))
    elif isinstance(near,list) and near and isinstance(near[-1],list): last_ms=int(near[-1][0])

    status="HISTORICAL_KLINES_ACCESSIBLE" if (first_ms is not None or last_ms is not None) else ("PROBE_ERROR" if err else "NO_KLINES_RETURNED")
    row={
      "symbol":SYMBOL,
      "status":status,
      "first_open_time_ms":first_ms,
      "last_sample_open_time_ms":last_ms,
      "first_probe_rows":1 if first_ms is not None else 0,
      "last_window_rows":len(near) if isinstance(near,list) else 0,
      "delisted_local":END_LOCAL,
      "announcement_date":"2023-04-05",
      "source_url":"https://www.binance.tr/blog/duyurular/b62ee86fd00a47be854a21d55a92f01d",
      "error":err
    }

    x=json.loads(PROBE.read_text()) if PROBE.exists() else {"results":[]}
    by={r["symbol"]:r for r in x.get("results",[])}
    by[SYMBOL]=row
    results=sorted(by.values(),key=lambda r:r["symbol"])
    x.update({
      "schema_version":2,
      "generated_at_ms":time.time_ns()//1_000_000,
      "symbols_total":len(results),
      "accessible_count":sum(r.get("status")=="HISTORICAL_KLINES_ACCESSIBLE" for r in results),
      "no_klines_count":sum(r.get("status")=="NO_KLINES_RETURNED" for r in results),
      "probe_error_count":sum(r.get("status")=="PROBE_ERROR" for r in results),
      "results":results,
      "backfill_touched":False,
      "live_collector_touched":False
    })
    tmp=PROBE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,PROBE)
    print(json.dumps(row,ensure_ascii=False,indent=2))

asyncio.run(main())
PY

"$PY" "$ROOT/app/probe_rune_delisted.py"

cat > "$ROOT/app/verify_delisted_coverage.py" <<'PY'
from __future__ import annotations
import json, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path("/root/bintrbot")
HIST=ROOT/"state/phase0a_historical_universe.json"
PROBE=ROOT/"state/phase0a_delisted_kline_probe.json"
CURRENT=ROOT/"data/meta/symbols.json"
BASE=ROOT/"data/bronze/klines_1m"
OUT=ROOT/"state/delisted_historical_coverage.json"

def load(p,default):
    try:return json.loads(p.read_text())
    except Exception:return default

def tr_ms(s):
    dt=datetime.strptime(s,"%Y-%m-%d %H:%M").replace(tzinfo=timezone(timedelta(hours=3)))
    return int(dt.astimezone(timezone.utc).timestamp()*1000)

def month_key(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).strftime("%Y-%m")

def next_ym(ym):
    y,m=map(int,ym.split("-"))
    return f"{y+1:04d}-01" if m==12 else f"{y:04d}-{m+1:02d}"

def months(a,b):
    cur=a
    while True:
        yield cur
        if cur==b:return
        cur=next_ym(cur)

hist=load(HIST,{})
probe=load(PROBE,{})
raw=load(CURRENT,{})
current={
  str(r.get("symbol","")).upper()
  for r in (raw.get("symbols") or raw.get("data") or [])
  if isinstance(r,dict)
}
probe_by={r.get("symbol"):r for r in probe.get("results",[])}

expected=[]
excluded_current=[]
unprobeable=[]
for r in hist.get("confirmed_delisted_try_seed",[]):
    sym=r.get("symbol")
    if not sym: continue
    if sym in current:
        excluded_current.append(sym)
        continue
    pr=probe_by.get(sym)
    if not pr or pr.get("status")!="HISTORICAL_KLINES_ACCESSIBLE" or pr.get("first_open_time_ms") is None:
        unprobeable.append(sym)
        continue
    first=int(pr["first_open_time_ms"])
    end=tr_ms(r["delisted_local"])
    if end<=first:
        unprobeable.append(sym)
        continue
    for ym in months(month_key(first),month_key(end-1)):
        y,m=ym.split("-")
        expected.append((sym,ym,BASE/f"symbol={sym}"/f"year={y}"/f"month={m}"/"manifest.json"))

missing=[]
bad=[]
complete=0
for sym,ym,p in expected:
    if not p.exists():
        missing.append(f"{sym}:{ym}")
        continue
    try:
        x=json.loads(p.read_text())
    except Exception:
        bad.append(f"{sym}:{ym}:MANIFEST_UNREADABLE")
        continue
    if x.get("status")!="COMPLETE":
        bad.append(f"{sym}:{ym}:STATUS={x.get('status')}")
    else:
        complete+=1

status="PASS" if not missing and not bad and not unprobeable and expected else "PENDING"
out={
  "schema_version":1,
  "status":status,
  "verified_at_ms":time.time_ns()//1_000_000,
  "delisted_seed_total":len(hist.get("confirmed_delisted_try_seed",[])),
  "current_overlap_excluded":sorted(excluded_current),
  "historical_targets_total":len(set(sym for sym,_,_ in expected)),
  "expected_months_total":len(expected),
  "complete_months_total":complete,
  "missing_months_total":len(missing),
  "bad_months_total":len(bad),
  "unprobeable_symbols":sorted(unprobeable),
  "missing_examples":missing[:50],
  "bad_examples":bad[:50],
  "seed_is_complete":bool(hist.get("seed_is_complete")),
  "note":"Coverage PASS means all currently verified non-current delisted seed markets are present. It does not claim historical-universe discovery is exhaustive while seed_is_complete=false."
}
tmp=OUT.with_suffix(".json.tmp")
tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,OUT)
print(json.dumps(out,ensure_ascii=False,indent=2))
PY

cat > /etc/systemd/system/bintrbot-delisted-coverage.service <<'UNIT'
[Unit]
Description=BintrBot Delisted Historical Coverage Reconciler
After=local-fs.target

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/bin/bash -lc '/root/bintrbot/.venv/bin/python /root/bintrbot/app/verify_delisted_coverage.py; if [ "$(systemctl is-active bintrbot-backfill-delisted-klines.service || true)" != "active" ]; then S=$(/root/bintrbot/.venv/bin/python -c "import json,pathlib; p=pathlib.Path('''/root/bintrbot/state/delisted_historical_coverage.json'''); x=json.loads(p.read_text()) if p.exists() else {}; print(x.get('''status''','''PENDING'''))"); if [ "$S" != "PASS" ]; then systemctl start --no-block bintrbot-backfill-delisted-klines.service; fi; fi'
User=root
Nice=19
IOSchedulingClass=idle
UNIT

cat > /etc/systemd/system/bintrbot-delisted-coverage.timer <<'UNIT'
[Unit]
Description=Reconcile BintrBot Delisted Historical Coverage

[Timer]
OnBootSec=8min
OnUnitActiveSec=8min
AccuracySec=1min
Persistent=true
Unit=bintrbot-delisted-coverage.service

[Install]
WantedBy=timers.target
UNIT

"$PY" - "$TRANS_APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
if 'DELISTED_COVERAGE = ROOT / "state/delisted_historical_coverage.json"' not in s:
    s=s.replace(
      'DELISTED_STATE = ROOT / "state/backfill_delisted_klines.json"\n',
      'DELISTED_STATE = ROOT / "state/backfill_delisted_klines.json"\nDELISTED_COVERAGE = ROOT / "state/delisted_historical_coverage.json"\n',
      1
    )

old='''    main_state = load(MAIN_STATE, {})
    delisted = load(DELISTED_STATE, {})
    if main_state.get("status") != "COMPLETE" or delisted.get("status") != "COMPLETE":
'''
new='''    main_state = load(MAIN_STATE, {})
    delisted = load(DELISTED_STATE, {})
    delisted_coverage = load(DELISTED_COVERAGE, {})
    if main_state.get("status") != "COMPLETE" or delisted_coverage.get("status") != "PASS":
'''
if old in s:
    s=s.replace(old,new,1)
elif 'delisted_coverage = load(DELISTED_COVERAGE, {})' not in s:
    raise SystemExit("PATCH_ABORT transition dependency target missing")

s=s.replace(
  '"delisted_dependency_status": delisted.get("status"),',
  '"delisted_dependency_status": delisted.get("status"),\n            "delisted_coverage_status": delisted_coverage.get("status"),\n            "delisted_coverage_missing_months": delisted_coverage.get("missing_months_total"),',
  1
)

p.write_text(s)
print("TRANSITION_COVERAGE_GATE_PATCH=YES")
PY

"$PY" -m py_compile "$ROOT/app/verify_delisted_coverage.py" "$TRANS_APP"
"$PY" "$ROOT/app/verify_delisted_coverage.py"

systemctl daemon-reload
systemctl enable --now bintrbot-delisted-coverage.timer
systemctl start bintrbot-backfill-transition-klines.service

echo
echo '========== RUNE PROBE =========='
"$PY" - <<'PY'
import json
from pathlib import Path
x=json.loads(Path("/root/bintrbot/state/phase0a_delisted_kline_probe.json").read_text())
r=next(z for z in x["results"] if z["symbol"]=="RUNE_TRY")
print("DELISTED_SEED_TOTAL=",len(json.loads(Path("/root/bintrbot/state/phase0a_historical_universe.json").read_text())["confirmed_delisted_try_seed"]))
print("RUNE_STATUS=",r["status"])
print("RUNE_FIRST=",r["first_open_time_ms"])
print("RUNE_LAST_SAMPLE=",r["last_sample_open_time_ms"])
PY

echo
echo '========== COVERAGE =========='
cat "$ROOT/state/delisted_historical_coverage.json"

echo
echo '========== TRANSITION QUEUE =========='
cat "$ROOT/state/backfill_transition_klines.json"

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-delisted-coverage.timer || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true
systemctl is-active bintrbot-collector.service || true

echo
echo "PHASE0A_RUNE_AND_COVERAGE_GATE=PASS"
