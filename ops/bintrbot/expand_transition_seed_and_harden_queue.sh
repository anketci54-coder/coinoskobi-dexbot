#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
META="$ROOT/state/phase0a_transition_universe.json"
PROBE="$ROOT/state/phase0a_transition_kline_probe.json"
APP="$ROOT/app/backfill_transition_klines.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$META" "$META.pre_transition_expand.$TS.bak"
cp -a "$PROBE" "$PROBE.pre_transition_expand.$TS.bak"
cp -a "$APP" "$APP.pre_dependency_hardening.$TS.bak"

"$PY" - "$META" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.setdefault("transitions", [])

extra=[
  {
    "old_symbol":"FTM_TRY",
    "new_symbol":"S_TRY",
    "trading_end_local":"2025-01-13 06:00",
    "new_trading_start_local":"2025-01-16 11:00",
    "transition_type":"TOKEN_SWAP_RENAME_CHAIN_TRANSITION",
    "swap_note":"1 FTM = 1 S",
    "reason":"Fantom project transition/rebrand to Sonic; Binance TR supported the FTM-to-S migration and documented changed Sonic tokenomics.",
    "mechanism":"FTM/TRY closed; FTM balances converted 1:1 to S; S/TRY opened after the migration window.",
    "result":"Old FTM market episode ends and S market episode begins. Raw ticker price series must not be treated as one uninterrupted market series.",
    "economic_continuity":"MIGRATION_CONTINUITY_WITH_TOKENOMICS_CHANGE",
    "price_series_continuity":"EPISODE_SPLIT_REQUIRED",
    "source":"BINANCE_TR_OFFICIAL",
    "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-fantom-ftm-token-takas%C4%B1n%C4%B1-ve-sonic-s-olarak-yeniden-adland%C4%B1rma-plan%C4%B1n%C4%B1-destekleyecek-1129"
  },
  {
    "old_symbol":"STRAX_TRY",
    "new_symbol":"STRAX_TRY",
    "trading_end_local":"2024-03-20 06:00",
    "new_trading_start_local":"2024-03-28 11:00",
    "transition_type":"TOKEN_SWAP_REDENOMINATION_SAME_TICKER",
    "swap_note":"1 old STRAX = 10 new STRAX",
    "reason":"Stratis token swap and redenomination. The Binance TR venue notice verifies the swap mechanics; deeper project rationale is not inferred beyond the evidence.",
    "mechanism":"STRAX/TRY closed; old STRAX balances converted at 1:10; STRAX/TRY reopened using the same ticker.",
    "result":"Same market ticker is reused across a denomination change. A raw continuous price series can create a false structural jump unless episode-aware/adjusted.",
    "economic_continuity":"MIGRATION_CONTINUITY_WITH_REDENOMINATION",
    "price_series_continuity":"EPISODE_SPLIT_AND_DENOMINATION_ADJUSTMENT_REQUIRED",
    "source":"BINANCE_TR_OFFICIAL",
    "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-stratis-strax-token-takas-ve-yeniden-adland%C4%B1rma-plan%C4%B1n%C4%B1-destekleyecek-fed25d53ba8645e898efa3d0c6293e50"
  }
]

by={r.get("old_symbol"):r for r in rows}
for r in extra:
    if r["old_symbol"] in by:
        by[r["old_symbol"]].update(r)
    else:
        rows.append(r)
        by[r["old_symbol"]]=r

rows.sort(key=lambda r:r.get("old_symbol",""))
x["transitions"]=rows
x["verified_seed_count"]=len(rows)
x["seed_is_complete"]=False
x["updated_at_ms"]=time.time_ns()//1_000_000

tmp=p.with_suffix(".json.tmp")
tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,p)
print("TRANSITION_SEED_COUNT=",len(rows))
PY

"$PY" - "$PROBE" "$META" <<'PY'
from __future__ import annotations
import asyncio, json, os, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import aiohttp

probe_path=Path(sys.argv[1])
meta_path=Path(sys.argv[2])
url="https://api.binance.me/api/v1/klines"
start_ms=1577836800000

probe=json.loads(probe_path.read_text())
meta=json.loads(meta_path.read_text())
existing={r["old_symbol"]:r for r in probe.get("results",[])}

targets=[
    r for r in meta["transitions"]
    if r["old_symbol"] in {"FTM_TRY","STRAX_TRY"}
]

current_raw=json.loads(Path("/root/bintrbot/data/meta/symbols.json").read_text())
current={
    str(r.get("symbol","")).upper()
    for r in (current_raw.get("symbols") or current_raw.get("data") or [])
    if isinstance(r,dict)
}

def utc_ms(local):
    dt=datetime.strptime(local,"%Y-%m-%d %H:%M").replace(tzinfo=timezone(timedelta(hours=3)))
    return int(dt.astimezone(timezone.utc).timestamp()*1000)

async def get(session, params):
    last=None
    for n in range(5):
        try:
            async with session.get(url,params=params,timeout=aiohttp.ClientTimeout(total=20)) as r:
                text=await r.text()
                if r.status==200:
                    x=json.loads(text)
                    return x.get("data",x) if isinstance(x,dict) else x
                last=f"HTTP_{r.status}:{text[:120]}"
                if r.status in (418,429) or r.status>=500:
                    await asyncio.sleep(min(2**n,15)); continue
                return {"error":last}
        except Exception as e:
            last=repr(e)
            await asyncio.sleep(min(2**n,15))
    return {"error":last}

async def main():
    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-transition-probe-v2/1.0"}) as session:
        for t in targets:
            symbol=t["old_symbol"]
            end=utc_ms(t["trading_end_local"])
            api=symbol.replace("_","")
            first=await get(session,{"symbol":api,"interval":"1m","startTime":start_ms,"endTime":end,"limit":1})
            await asyncio.sleep(0.5)
            near=await get(session,{"symbol":api,"interval":"1m","startTime":max(start_ms,end-7*86400000),"endTime":end,"limit":1000})
            await asyncio.sleep(0.5)

            err=None; first_ms=None; last_ms=None
            if isinstance(first,dict): err=first.get("error")
            elif isinstance(first,list) and first and isinstance(first[0],list): first_ms=int(first[0][0])
            if isinstance(near,dict): err=(err+" | " if err else "")+str(near.get("error"))
            elif isinstance(near,list) and near and isinstance(near[-1],list): last_ms=int(near[-1][0])

            status="HISTORICAL_KLINES_ACCESSIBLE" if (first_ms is not None or last_ms is not None) else ("PROBE_ERROR" if err else "NO_KLINES_RETURNED")
            row={
                **t,
                "status":status,
                "currently_active_same_symbol":symbol in current,
                "first_open_time_ms":first_ms,
                "last_sample_open_time_ms":last_ms,
                "error":err
            }
            existing[symbol]=row
            print(symbol,status,"current=",symbol in current,"first=",first_ms,"last=",last_ms,flush=True)

    results=sorted(existing.values(),key=lambda r:r["old_symbol"])
    out={
        "schema_version":2,
        "generated_at_ms":time.time_ns()//1_000_000,
        "symbols_total":len(results),
        "accessible_count":sum(r["status"]=="HISTORICAL_KLINES_ACCESSIBLE" for r in results),
        "no_klines_count":sum(r["status"]=="NO_KLINES_RETURNED" for r in results),
        "probe_error_count":sum(r["status"]=="PROBE_ERROR" for r in results),
        "current_same_symbol_count":sum(bool(r.get("currently_active_same_symbol")) for r in results),
        "results":results,
        "backfill_touched":False,
        "collector_touched":False
    }
    tmp=probe_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,probe_path)
    print(json.dumps({k:v for k,v in out.items() if k!="results"},ensure_ascii=False,indent=2))

asyncio.run(main())
PY

"$PY" - "$APP" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

if 'MAIN_STATE = ROOT / "state/backfill_klines.json"' not in s:
    s=s.replace(
        'DELISTED_STATE = ROOT / "state/backfill_delisted_klines.json"\n',
        'DELISTED_STATE = ROOT / "state/backfill_delisted_klines.json"\nMAIN_STATE = ROOT / "state/backfill_klines.json"\nCURRENT = ROOT / "data/meta/symbols.json"\n',
        1
    )

old='''async def main():
    delisted = load(DELISTED_STATE, {})
    if delisted.get("status") != "COMPLETE":
        state = load(STATE, {})
        state.update({
            "schema_version": 1,
            "status": "WAITING_ON_DELISTED_BACKFILL",
            "dependency_status": delisted.get("status"),
            "dependency_jobs_remaining": delisted.get("jobs_remaining"),
            "updated_at_ms": now_ms(),
            "backfill_started": False,
        })
        atomic_json(STATE, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    meta = load(META, {})
    probe = load(PROBE, {})
'''
new='''async def main():
    main_state = load(MAIN_STATE, {})
    delisted = load(DELISTED_STATE, {})
    if main_state.get("status") != "COMPLETE" or delisted.get("status") != "COMPLETE":
        state = load(STATE, {})
        state.update({
            "schema_version": 2,
            "status": "WAITING_ON_HISTORICAL_DEPENDENCIES",
            "main_dependency_status": main_state.get("status"),
            "main_dependency_jobs_remaining": main_state.get("jobs_remaining"),
            "delisted_dependency_status": delisted.get("status"),
            "delisted_dependency_jobs_remaining": delisted.get("jobs_remaining"),
            "updated_at_ms": now_ms(),
            "backfill_started": False,
        })
        atomic_json(STATE, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    meta = load(META, {})
    probe = load(PROBE, {})
    current_raw = load(CURRENT, {})
    current_symbols = {
        str(r.get("symbol", "")).upper()
        for r in (current_raw.get("symbols") or current_raw.get("data") or [])
        if isinstance(r, dict)
    }
'''
if old in s:
    s=s.replace(old,new,1)
elif '"WAITING_ON_HISTORICAL_DEPENDENCIES"' not in s:
    raise SystemExit("PATCH_ABORT dependency block not found")

old2='''        if not symbol or not pr:
            continue
        first_ms = int(pr["first_open_time_ms"])
'''
new2='''        if not symbol or not pr:
            continue
        if symbol in current_symbols:
            continue
        first_ms = int(pr["first_open_time_ms"])
'''
if old2 in s:
    s=s.replace(old2,new2,1)
elif 'if symbol in current_symbols:' not in s:
    raise SystemExit("PATCH_ABORT current exclusion block not found")

old3='''        "dependency_status": "COMPLETE",
        "backfill_started": True,
'''
new3='''        "main_dependency_status": "COMPLETE",
        "delisted_dependency_status": "COMPLETE",
        "current_symbols_excluded": sorted(
            t.get("old_symbol") for t in meta.get("transitions", [])
            if t.get("old_symbol") in current_symbols
        ),
        "backfill_started": True,
'''
if old3 in s:
    s=s.replace(old3,new3,1)

p.write_text(s)
print("QUEUE_HARDEN_PATCH=YES")
PY

"$PY" -m py_compile "$APP"

# Run the oneshot once so its state reflects the stricter dependency gate now.
systemctl start bintrbot-backfill-transition-klines.service

echo
echo '========== EXPANDED TRANSITION PROBE =========='
"$PY" - <<'PY'
import json
from pathlib import Path
x=json.loads(Path("/root/bintrbot/state/phase0a_transition_kline_probe.json").read_text())
print("SYMBOLS_TOTAL=",x["symbols_total"])
print("ACCESSIBLE=",x["accessible_count"])
print("NO_KLINES=",x["no_klines_count"])
print("PROBE_ERRORS=",x["probe_error_count"])
print("CURRENT_SAME_SYMBOL=",x["current_same_symbol_count"])
for sym in ("FTM_TRY","STRAX_TRY"):
    r=next(z for z in x["results"] if z["old_symbol"]==sym)
    print(sym,"->",r["new_symbol"],r["status"],"current=",r["currently_active_same_symbol"],"ratio=",r.get("swap_note"),"first=",r["first_open_time_ms"],"last=",r["last_sample_open_time_ms"])
PY

echo
echo '========== QUEUE STATE =========='
cat "$ROOT/state/backfill_transition_klines.json"

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true
systemctl is-active bintrbot-collector.service || true
echo "PHASE0A_TRANSITION_EXPAND_AND_QUEUE_HARDEN=PASS"
