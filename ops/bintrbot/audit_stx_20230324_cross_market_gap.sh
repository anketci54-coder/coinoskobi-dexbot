#!/usr/bin/env bash
set -euo pipefail
PY=/root/bintrbot/.venv/bin/python

"$PY" - <<'PY'
from __future__ import annotations
import json, urllib.parse, urllib.request
from datetime import datetime, timezone

URL="https://api.binance.me/api/v1/klines"
SYMBOLS=["STX_TRY","BTC_TRY","ETH_TRY","BNB_TRY","CFX_TRY","AGIX_TRY"]
START=1679655600000  # 2023-03-24 11:00 UTC
END=1679668200000    # 2023-03-24 14:30 UTC
TARGET_A=1679661600000  # 12:40 UTC
TARGET_B=1679666340000  # 13:59 UTC

def iso(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()

def fetch(sym):
    q=urllib.parse.urlencode({
        "symbol":sym.replace("_",""),
        "interval":"1m",
        "startTime":START,
        "endTime":END,
        "limit":1000,
    })
    req=urllib.request.Request(URL+"?"+q, headers={"User-Agent":"bintrbot-gap-audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        x=json.loads(r.read().decode())
    if isinstance(x,dict):
        x=x.get("data",x)
    return x if isinstance(x,list) else []

for sym in SYMBOLS:
    rows=fetch(sym)
    ts=sorted(int(r[0]) for r in rows)
    present=set(ts)
    expected=list(range(START,END+1,60000))
    missing=[t for t in expected if t not in present]

    groups=[]
    if missing:
        a=prev=missing[0]
        for t in missing[1:]:
            if t==prev+60000:
                prev=t
            else:
                groups.append((a,prev))
                a=prev=t
        groups.append((a,prev))

    target_missing=sum(1 for t in range(TARGET_A,TARGET_B+1,60000) if t not in present)
    print(f"=== {sym} ===")
    print("ROWS=",len(rows))
    print("FIRST=",iso(ts[0]) if ts else None)
    print("LAST=",iso(ts[-1]) if ts else None)
    print("MISSING_TOTAL=",len(missing))
    print("TARGET_WINDOW_MISSING=",target_missing)
    for a,b in groups[:10]:
        print("GAP=",iso(a),"->",iso(b),"minutes=",((b-a)//60000)+1)
    print()

print("AUDIT_WINDOW_UTC=2023-03-24T11:00:00Z..2023-03-24T14:30:00Z")
print("STX_TARGET_GAP_UTC=2023-03-24T12:40:00Z..2023-03-24T13:59:00Z")
PY
