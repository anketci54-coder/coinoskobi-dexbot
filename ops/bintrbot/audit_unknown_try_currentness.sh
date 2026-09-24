#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/audit_unknown_try_currentness.py" <<'PY'
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

ROOT=Path("/root/bintrbot")
DISC=ROOT/"state/phase0a_unknown_historical_try_discovery.json"
CURRENT=ROOT/"data/meta/symbols.json"
OUT=ROOT/"state/phase0a_unknown_try_currentness.json"
URL="https://api.binance.me/api/v1/klines"

def load(p,default):
    try:return json.loads(p.read_text())
    except Exception:return default

def atomic(p,obj):
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,p)

def iso(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat() if ms else None

async def get(session,symbol):
    last=None
    for n in range(5):
        try:
            async with session.get(
                URL,
                params={"symbol":symbol.replace("_",""),"interval":"1m","limit":2},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                text=await r.text()
                if r.status==200:
                    x=json.loads(text)
                    return x.get("data",x) if isinstance(x,dict) else x, None
                last=f"HTTP_{r.status}:{text[:160]}"
                if r.status in (418,429) or r.status>=500:
                    await asyncio.sleep(min(2**n,15)); continue
                return None,last
        except Exception as e:
            last=repr(e)
            await asyncio.sleep(min(2**n,15))
    return None,last

async def main():
    now=int(time.time()*1000)
    d=load(DISC,{})
    raw=load(CURRENT,{})
    current={
        str(r.get("symbol","")).upper()
        for r in (raw.get("symbols") or raw.get("data") or [])
        if isinstance(r,dict)
    }
    symbols=[r["symbol"] for r in d.get("found",[])]
    rows=[]

    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-currentness-audit/1.0"}) as s:
        for sym in symbols:
            data,err=await get(s,sym)
            last_ms=None
            if isinstance(data,list) and data and isinstance(data[-1],list):
                last_ms=int(data[-1][0])
            age_min=(now-last_ms)/60000 if last_ms is not None else None
            live=bool(age_min is not None and age_min <= 10)
            row={
                "symbol":sym,
                "in_current_snapshot":sym in current,
                "latest_open_time_ms":last_ms,
                "latest_open_time_utc":iso(last_ms),
                "latest_age_minutes":round(age_min,3) if age_min is not None else None,
                "producing_current_klines":live,
                "error":err,
            }
            rows.append(row)
            print(
                sym,
                "snapshot=",sym in current,
                "live=",live,
                "latest=",iso(last_ms),
                "age_min=",row["latest_age_minutes"],
                "error=",err,
                flush=True
            )
            await asyncio.sleep(0.4)

    live_missing=[r["symbol"] for r in rows if r["producing_current_klines"] and not r["in_current_snapshot"]]
    historical_only=[r["symbol"] for r in rows if not r["producing_current_klines"] and r["latest_open_time_ms"] is not None]
    errors=[r for r in rows if r["error"]]

    out={
        "schema_version":1,
        "status":"PASS" if not errors else "PASS_WITH_ERRORS",
        "audited_at_ms":now,
        "audited_symbols":len(rows),
        "live_but_missing_from_current_snapshot":live_missing,
        "live_but_missing_count":len(live_missing),
        "historical_only_symbols":historical_only,
        "historical_only_count":len(historical_only),
        "errors":errors,
        "rows":rows,
        "current_snapshot_requires_repair":bool(live_missing),
        "canonicalized_automatically":False,
    }
    atomic(OUT,out)
    print(json.dumps({k:v for k,v in out.items() if k not in {"rows","errors"}},ensure_ascii=False,indent=2))

asyncio.run(main())
PY

"$PY" -m py_compile "$ROOT/app/audit_unknown_try_currentness.py"
"$PY" "$ROOT/app/audit_unknown_try_currentness.py"

echo
echo '========== CURRENTNESS RESULT =========='
cat "$ROOT/state/phase0a_unknown_try_currentness.json"

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true
systemctl is-active bintrbot-collector.service || true

echo
echo "PHASE0A_UNKNOWN_TRY_CURRENTNESS_AUDIT=PASS"
