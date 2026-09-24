#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
META="$ROOT/state/phase0a_transition_universe.json"
OUT="$ROOT/state/phase0a_transition_kline_probe.json"

cat > "$META" <<'JSON'
{
  "schema_version": 1,
  "status": "DISCOVERY_REQUIRED",
  "scope": "BINANCE_TR_TRY_TOKEN_TRANSITIONS",
  "seed_is_complete": false,
  "transitions": [
    {
      "old_symbol":"COCOS_TRY","new_symbol":"COMBO_TRY",
      "trading_end_local":"2023-05-29 11:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/duyurular/183db590e72b4e5389af82f2dd04f3c8"
    },
    {
      "old_symbol":"OCEAN_TRY","new_symbol":"FET_TRY",
      "trading_end_local":"2024-07-01 06:00",
      "transition_type":"TOKEN_MERGER",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-fetchai-fet-ocean-protocol-ocean-ve-singularitynet-agix-token-birle%C5%9Fmesini-destekleyecek-1011"
    },
    {
      "old_symbol":"AGIX_TRY","new_symbol":"FET_TRY",
      "trading_end_local":"2024-07-01 06:00",
      "transition_type":"TOKEN_MERGER",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-fetchai-fet-ocean-protocol-ocean-ve-singularitynet-agix-token-birle%C5%9Fmesini-destekleyecek-1011"
    },
    {
      "old_symbol":"GAL_TRY","new_symbol":"G_TRY",
      "trading_end_local":"2024-07-15 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 GAL = 60 G",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-galxe-gal-token-takas%C4%B1n%C4%B1-yeniden-adland%C4%B1rmay%C4%B1-ve-gravity-g-olarak-marka-de%C4%9Fi%C5%9Fimini-destekleyecek-1018"
    },
    {
      "old_symbol":"RNDR_TRY","new_symbol":"RENDER_TRY",
      "trading_end_local":"2024-07-22 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 RNDR = 1 RENDER",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/Announcements/887b8d485ff2426a93d053259af35835"
    },
    {
      "old_symbol":"FRONT_TRY","new_symbol":"SLF_TRY",
      "trading_end_local":"2024-08-27 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 FRONT = 1 SLF",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/Announcements/0f3a4143c3414db3a25a93f0d664b374"
    },
    {
      "old_symbol":"MATIC_TRY","new_symbol":"POL_TRY",
      "trading_end_local":"2024-09-10 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 MATIC = 1 POL",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/blog/Announcements/a8a7fdedf7954a58a45804f121bb1f66"
    },
    {
      "old_symbol":"DAR_TRY","new_symbol":"D_TRY",
      "trading_end_local":"2025-01-06 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-mines-of-dalarnia-dar-token-takas%C4%B1n%C4%B1-ve-dar-open-network-d-olarak-yeniden-adland%C4%B1rma-plan%C4%B1n%C4%B1-destekleyecek-1127"
    },
    {
      "old_symbol":"BNX_TRY","new_symbol":"FORM_TRY",
      "trading_end_local":"2025-03-18 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 BNX = 1 FORM",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/Announcements/70733afbc2f7430e94e12045693ccb7b"
    },
    {
      "old_symbol":"MKR_TRY","new_symbol":"SKY_TRY",
      "trading_end_local":"2025-09-15 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 MKR = 24000 SKY",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-maker-mkr-token-takas%C4%B1n%C4%B1-ve-sky-sky-olarak-yeniden-adland%C4%B1rma-plan%C4%B1n%C4%B1-destekleyecek-1291"
    },
    {
      "old_symbol":"OMNI_TRY","new_symbol":"NOM_TRY",
      "trading_end_local":"2025-09-29 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 OMNI = 75 NOM",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/Announcements/f0046755bbdc43ec953a2f81c780b49b"
    },
    {
      "old_symbol":"OM_TRY","new_symbol":"MANTRA_TRY",
      "trading_end_local":"2026-03-02 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 OM = 4 MANTRA",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/Announcements/1380327db0e7450eb87dbfb22305a595"
    },
    {
      "old_symbol":"TON_TRY","new_symbol":"GRAM_TRY",
      "trading_end_local":"2026-06-30 06:00",
      "transition_type":"TOKEN_SWAP_RENAME",
      "swap_note":"1 TON = 1 GRAM",
      "source":"BINANCE_TR_OFFICIAL",
      "source_url":"https://www.binance.tr/tr/blog/Announcements/3e344a853203414aa8f55fd74a04f07c"
    }
  ],
  "notes":[
    "This is a verified seed, not an exhaustive claim.",
    "Token transition/removal is kept separate from ordinary delisting.",
    "Historical universe inclusion does not imply asset identity continuity across a swap or rename."
  ]
}
JSON

cat > "$ROOT/app/probe_transition_klines.py" <<'PY'
from __future__ import annotations
import asyncio, json, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import aiohttp

ROOT=Path("/root/bintrbot")
META=ROOT/"state/phase0a_transition_universe.json"
CURRENT=ROOT/"data/meta/symbols.json"
OUT=ROOT/"state/phase0a_transition_kline_probe.json"
URL="https://api.binance.me/api/v1/klines"
START_MS=1577836800000

def end_ms(local):
    dt=datetime.strptime(local,"%Y-%m-%d %H:%M").replace(tzinfo=timezone(timedelta(hours=3)))
    return int(dt.astimezone(timezone.utc).timestamp()*1000)

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
    meta=json.loads(META.read_text())
    raw=json.loads(CURRENT.read_text())
    current={
        str(x.get("symbol","")).upper()
        for x in (raw.get("symbols") or raw.get("data") or [])
        if isinstance(x,dict)
    }
    results=[]
    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-transition-probe/1.0"}) as session:
        for i,t in enumerate(meta["transitions"],1):
            symbol=t["old_symbol"]
            api=symbol.replace("_","")
            end=end_ms(t["trading_end_local"])
            first=await get(session,{"symbol":api,"interval":"1m","startTime":START_MS,"endTime":end,"limit":1})
            await asyncio.sleep(0.5)
            near=await get(session,{
                "symbol":api,"interval":"1m",
                "startTime":max(START_MS,end-7*24*3600_000),
                "endTime":end,
                "limit":1000
            })
            await asyncio.sleep(0.5)

            err=None; first_ms=None; last_ms=None
            if isinstance(first,dict):
                err=first.get("error")
            elif isinstance(first,list) and first and isinstance(first[0],list):
                first_ms=int(first[0][0])
            if isinstance(near,dict):
                err=(err+" | " if err else "")+str(near.get("error"))
            elif isinstance(near,list) and near and isinstance(near[-1],list):
                last_ms=int(near[-1][0])

            status="HISTORICAL_KLINES_ACCESSIBLE" if (first_ms is not None or last_ms is not None) else ("PROBE_ERROR" if err else "NO_KLINES_RETURNED")
            r={
                **t,
                "status":status,
                "currently_active_same_symbol":symbol in current,
                "first_open_time_ms":first_ms,
                "last_sample_open_time_ms":last_ms,
                "error":err
            }
            results.append(r)
            print(f"{i}/{len(meta['transitions'])} {symbol} {status} current={symbol in current} first={first_ms} last={last_ms}",flush=True)

    out={
        "schema_version":1,
        "generated_at_ms":time.time_ns()//1_000_000,
        "symbols_total":len(results),
        "accessible_count":sum(r["status"]=="HISTORICAL_KLINES_ACCESSIBLE" for r in results),
        "no_klines_count":sum(r["status"]=="NO_KLINES_RETURNED" for r in results),
        "probe_error_count":sum(r["status"]=="PROBE_ERROR" for r in results),
        "current_same_symbol_count":sum(r["currently_active_same_symbol"] for r in results),
        "results":results,
        "backfill_touched":False,
        "collector_touched":False
    }
    atomic(OUT,out)
    print(json.dumps({k:v for k,v in out.items() if k!="results"},ensure_ascii=False,indent=2))

asyncio.run(main())
PY

"$PY" -m py_compile "$ROOT/app/probe_transition_klines.py"
"$PY" "$ROOT/app/probe_transition_klines.py"

echo
echo '========== TRANSITION PROBE =========='
"$PY" - <<'PY'
import json
from pathlib import Path
x=json.loads(Path("/root/bintrbot/state/phase0a_transition_kline_probe.json").read_text())
print("SYMBOLS_TOTAL=",x["symbols_total"])
print("ACCESSIBLE=",x["accessible_count"])
print("NO_KLINES=",x["no_klines_count"])
print("PROBE_ERRORS=",x["probe_error_count"])
print("CURRENT_SAME_SYMBOL=",x["current_same_symbol_count"])
for r in x["results"]:
    print(r["old_symbol"],"->",r["new_symbol"],r["status"],"current_old_symbol=",r["currently_active_same_symbol"],"first=",r["first_open_time_ms"],"last=",r["last_sample_open_time_ms"])
PY

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-collector.service || true
echo "PHASE0A_TRANSITION_PROBE=PASS"
