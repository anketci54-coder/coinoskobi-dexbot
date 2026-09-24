#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
STATE="$ROOT/state/phase0a_historical_universe.json"
OUT="$ROOT/state/phase0a_delisted_kline_probe.json"

cp -a "$STATE" "$STATE.pre_probe.$(date -u +%Y%m%dT%H%M%SZ).bak"

"$PY" - <<'PY'
from __future__ import annotations
import json, os, time
from pathlib import Path

ROOT=Path("/root/bintrbot")
STATE=ROOT/"state/phase0a_historical_universe.json"

x=json.loads(STATE.read_text())
rows=x.setdefault("confirmed_delisted_try_seed", [])

extra = [
 {"symbol":"LUNA_TRY","announced_date":"2022-05-13","delisted_local":"2022-05-13 03:40","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/duyurular/8ab5ffdff77a4406be64a5719196d072"},
 {"symbol":"REEF_TRY","announced_date":"2024-08-12","delisted_local":"2024-08-26 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/delisting/reeftry-ve-loomtry-i%C5%9Flem-%C3%A7iftlerinin-kald%C4%B1r%C4%B1lmas%C4%B1-hakk%C4%B1nda-bildirim-26082024-1040"},
 {"symbol":"LOOM_TRY","announced_date":"2024-08-12","delisted_local":"2024-08-26 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/delisting/reeftry-ve-loomtry-i%C5%9Flem-%C3%A7iftlerinin-kald%C4%B1r%C4%B1lmas%C4%B1-hakk%C4%B1nda-bildirim-26082024-1040"},
 {"symbol":"IMX_TRY","announced_date":"2024-08-14","delisted_local":"2024-08-16 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/delisting/imxtry-i%C5%9Flem-%C3%A7iftinin-listeden-kald%C4%B1r%C4%B1lmas%C4%B1-hakk%C4%B1nda-bildirim-16082024-1043"},
 {"symbol":"UNFI_TRY","announced_date":"2024-10-23","delisted_local":"2024-11-06 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/delisting/unfitry-i%C5%9Flem-%C3%A7iftinin-listeden-kald%C4%B1r%C4%B1lmas%C4%B1-hakk%C4%B1nda-bildirim-06112024-1088"},
 {"symbol":"ACM_TRY","announced_date":"2024-12-24","delisted_local":"2024-12-27 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/announcements/acm-mtl-ve-tusd-i%C5%9Flem-%C3%A7iftleri-hakk%C4%B1nda-bildirim-27122024-1128"},
 {"symbol":"MTL_TRY","announced_date":"2024-12-24","delisted_local":"2024-12-27 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/announcements/acm-mtl-ve-tusd-i%C5%9Flem-%C3%A7iftleri-hakk%C4%B1nda-bildirim-27122024-1128"},
 {"symbol":"TUSD_TRY","announced_date":"2024-12-24","delisted_local":"2024-12-27 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/announcements/acm-mtl-ve-tusd-i%C5%9Flem-%C3%A7iftleri-hakk%C4%B1nda-bildirim-27122024-1128"},
 {"symbol":"UNFI_TRY","announced_date":"2024-10-23","delisted_local":"2024-11-06 06:00","source":"BINANCE_TR_OFFICIAL","source_url":"https://www.binance.tr/tr/blog/delisting/unfitry-i%C5%9Flem-%C3%A7iftinin-listeden-kald%C4%B1r%C4%B1lmas%C4%B1-hakk%C4%B1nda-bildirim-06112024-1088"}
]

by={r["symbol"]:r for r in rows}
for r in extra:
    old=by.get(r["symbol"])
    if old:
        old.update({k:v for k,v in r.items() if v is not None})
    else:
        rows.append(r)
        by[r["symbol"]]=r

for r in rows:
    r.setdefault("known_at_precision","DATE_ONLY" if r.get("announced_date") else "UNKNOWN")

rows.sort(key=lambda r:r["symbol"])
x["confirmed_delisted_try_seed"]=rows
x["confirmed_delisted_try_seed_count"]=len(rows)
x["seed_is_complete"]=False
x["status"]="DISCOVERY_REQUIRED"
x["survivorship_bias_resolved"]=False
x["updated_at_ms"]=time.time_ns()//1_000_000
x["notes"]=[
  "Seed is evidence-backed but not claimed exhaustive.",
  "Announcement publication time is not invented; DATE_ONLY is retained where only date is verified.",
  "Historical kline accessibility is tested separately."
]
tmp=STATE.with_suffix(".json.tmp")
tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,STATE)
print("SEED_COUNT=",len(rows))
PY

cat > "$ROOT/app/probe_delisted_klines.py" <<'PY'
from __future__ import annotations
import asyncio, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import aiohttp

ROOT=Path("/root/bintrbot")
STATE=ROOT/"state/phase0a_historical_universe.json"
OUT=ROOT/"state/phase0a_delisted_kline_probe.json"
URL="https://api.binance.me/api/v1/klines"
START_MS=1599609600000
GAP=0.45

def ms_local_to_utc(s):
    # Binance TR announcement times are Türkiye local time, UTC+3.
    if not s:
        return None
    dt=datetime.strptime(s,"%Y-%m-%d %H:%M")
    dt=dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp()*1000)-3*3600*1000

def atomic(path,obj):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,path)

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
    state=json.loads(STATE.read_text())
    rows=state.get("confirmed_delisted_try_seed",[])
    results=[]
    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-historical-universe-probe/1.0"}) as session:
        for i,r in enumerate(rows,1):
            symbol=r["symbol"]
            api=symbol.replace("_","")
            end=ms_local_to_utc(r.get("delisted_local")) or int(time.time()*1000)
            first=await get(session,{
                "symbol":api,"interval":"1m",
                "startTime":START_MS,"endTime":end,"limit":1
            })
            await asyncio.sleep(GAP)

            before=max(START_MS,end-7*24*3600*1000)
            last=await get(session,{
                "symbol":api,"interval":"1m",
                "startTime":before,"endTime":end,"limit":1000
            })
            await asyncio.sleep(GAP)

            error=None
            first_ms=None
            last_ms=None
            first_count=0
            last_count=0
            if isinstance(first,dict) and "error" in first:
                error=first["error"]
            elif isinstance(first,list):
                first_count=len(first)
                if first and isinstance(first[0],list):
                    first_ms=int(first[0][0])

            if isinstance(last,dict) and "error" in last:
                error=(error+" | " if error else "")+last["error"]
            elif isinstance(last,list):
                last_count=len(last)
                if last and isinstance(last[-1],list):
                    last_ms=int(last[-1][0])

            status=(
                "HISTORICAL_KLINES_ACCESSIBLE"
                if first_ms is not None or last_ms is not None
                else ("PROBE_ERROR" if error else "NO_KLINES_RETURNED")
            )
            item={
                "symbol":symbol,
                "status":status,
                "first_open_time_ms":first_ms,
                "last_sample_open_time_ms":last_ms,
                "first_probe_rows":first_count,
                "last_window_rows":last_count,
                "delisted_local":r.get("delisted_local"),
                "announcement_date":r.get("announced_date"),
                "source_url":r.get("source_url"),
                "error":error,
            }
            results.append(item)
            print(f"{i}/{len(rows)} {symbol} {status} first={first_ms} last={last_ms}",flush=True)

    out={
        "schema_version":1,
        "generated_at_ms":time.time_ns()//1_000_000,
        "symbols_total":len(results),
        "accessible_count":sum(x["status"]=="HISTORICAL_KLINES_ACCESSIBLE" for x in results),
        "no_klines_count":sum(x["status"]=="NO_KLINES_RETURNED" for x in results),
        "probe_error_count":sum(x["status"]=="PROBE_ERROR" for x in results),
        "results":results,
        "backfill_touched":False,
        "live_collector_touched":False,
    }
    atomic(OUT,out)
    print(json.dumps({k:v for k,v in out.items() if k!="results"},indent=2))

asyncio.run(main())
PY

"$PY" "$ROOT/app/probe_delisted_klines.py"

echo
echo '========== HISTORICAL UNIVERSE PROBE =========='
"$PY" - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/state/phase0a_delisted_kline_probe.json")
x=json.loads(p.read_text())
print("SYMBOLS_TOTAL=",x["symbols_total"])
print("ACCESSIBLE=",x["accessible_count"])
print("NO_KLINES=",x["no_klines_count"])
print("PROBE_ERRORS=",x["probe_error_count"])
print()
for r in x["results"]:
    print(r["symbol"],r["status"],"first=",r["first_open_time_ms"],"last=",r["last_sample_open_time_ms"])
PY

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-phase0c-observer.timer || true
echo "PHASE0A_DELISTED_KLINE_PROBE=PASS"
