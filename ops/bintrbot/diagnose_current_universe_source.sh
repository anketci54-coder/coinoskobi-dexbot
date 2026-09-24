#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/diagnose_current_universe_source.py" <<'PY'
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path("/root/bintrbot")
SYMBOLS=ROOT/"data/meta/symbols.json"
IDENTITY=ROOT/"data/meta/identity/current_try_core.json"
COLLECTOR=ROOT/"app/collector.py"
OUT=ROOT/"state/phase0a_current_universe_source_diagnosis.json"
URL="https://www.binance.tr/open/v1/common/symbols"

def load(p,default):
    try:return json.loads(p.read_text())
    except Exception:return default

def atomic(p,obj):
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,p)

def normalize(rows):
    out={}
    for r in rows:
        if not isinstance(r,dict):
            continue
        sym=str(r.get("symbol") or r.get("s") or "").strip().upper()
        base=str(r.get("baseAsset") or r.get("base_asset") or r.get("base") or "").strip().upper()
        quote=str(r.get("quoteAsset") or r.get("quote_asset") or r.get("quote") or "").strip().upper()
        if not quote and "_" in sym:
            _,quote=sym.rsplit("_",1)
        if quote=="TRY" and sym:
            out[sym]=r
    return out

req=Request(URL,headers={"User-Agent":"bintrbot-current-universe-diagnosis/1.0"})
with urlopen(req,timeout=30) as resp:
    official_raw=json.loads(resp.read().decode())

data=official_raw.get("data",{}) if isinstance(official_raw,dict) else {}
official_rows=(data.get("list") if isinstance(data,dict) else None) or []
official=normalize(official_rows)

local_raw=load(SYMBOLS,{})
if isinstance(local_raw,dict):
    local_rows=local_raw.get("symbols") or local_raw.get("data") or local_raw.get("list") or []
    if isinstance(local_rows,dict):
        local_rows=local_rows.get("list") or []
else:
    local_rows=local_raw if isinstance(local_raw,list) else []
local=normalize(local_rows)

ident=load(IDENTITY,{})
identity_symbols={
    str(r.get("symbol","")).upper()
    for r in ident.get("markets",[])
    if isinstance(r,dict) and r.get("symbol")
}

missing_local=sorted(set(official)-set(local))
extra_local=sorted(set(local)-set(official))
missing_identity=sorted(set(official)-identity_symbols)
extra_identity=sorted(identity_symbols-set(official))

def stat(p):
    if not p.exists():
        return None
    st=p.stat()
    return {
        "path":str(p),
        "size":st.st_size,
        "mtime_ms":int(st.st_mtime*1000),
        "mtime_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(st.st_mtime)),
    }

collector_refs=[]
if COLLECTOR.exists():
    for no,line in enumerate(COLLECTOR.read_text(errors="replace").splitlines(),1):
        if re.search(r"symbols\.json|common/symbols|quoteAsset|symbol_type|type.?==|type.?in|TRY",line,re.I):
            collector_refs.append({"line":no,"text":line[:300]})

try:
    unit=subprocess.run(
        ["systemctl","show","bintrbot-collector.service","-p","ExecStart","-p","ActiveState","-p","MainPID"],
        text=True,capture_output=True,check=False
    ).stdout.strip().splitlines()
except Exception as e:
    unit=[repr(e)]

missing_details=[]
for s in missing_local:
    r=official[s]
    missing_details.append({
        "symbol":s,
        "type":r.get("type"),
        "baseAsset":r.get("baseAsset"),
        "quoteAsset":r.get("quoteAsset"),
        "status":r.get("status"),
    })

out={
    "schema_version":1,
    "status":"PASS",
    "diagnosed_at_ms":time.time_ns()//1_000_000,
    "official_source":URL,
    "official_api_code":official_raw.get("code") if isinstance(official_raw,dict) else None,
    "official_api_msg":official_raw.get("msg") if isinstance(official_raw,dict) else None,
    "official_try_count":len(official),
    "local_symbols_try_count":len(local),
    "identity_snapshot_try_count":len(identity_symbols),
    "missing_from_local_count":len(missing_local),
    "missing_from_local":missing_local,
    "missing_from_local_details":missing_details,
    "local_not_in_official_count":len(extra_local),
    "local_not_in_official":extra_local,
    "missing_from_identity_count":len(missing_identity),
    "missing_from_identity":missing_identity,
    "identity_not_in_official_count":len(extra_identity),
    "identity_not_in_official":extra_identity,
    "zama_official":official.get("ZAMA_TRY"),
    "zama_local":local.get("ZAMA_TRY"),
    "zama_identity":next((r for r in ident.get("markets",[]) if r.get("symbol")=="ZAMA_TRY"),None),
    "files":{
        "symbols":stat(SYMBOLS),
        "identity_current":stat(IDENTITY),
        "collector":stat(COLLECTOR),
    },
    "collector_symbol_source_refs":collector_refs,
    "collector_service":unit,
    "mutations_performed":False,
}
atomic(OUT,out)

summary={
    "OFFICIAL_TRY":len(official),
    "LOCAL_SYMBOLS_TRY":len(local),
    "IDENTITY_TRY":len(identity_symbols),
    "MISSING_LOCAL":missing_local,
    "LOCAL_NOT_OFFICIAL":extra_local,
    "MISSING_IDENTITY":missing_identity,
    "ZAMA_OFFICIAL_TYPE":(official.get("ZAMA_TRY") or {}).get("type"),
    "ZAMA_IN_LOCAL":"ZAMA_TRY" in local,
    "ZAMA_IN_IDENTITY":"ZAMA_TRY" in identity_symbols,
}
print(json.dumps(summary,ensure_ascii=False,indent=2))
print("\n=== FILES ===")
print(json.dumps(out["files"],ensure_ascii=False,indent=2))
print("\n=== COLLECTOR SYMBOL SOURCE REFS ===")
for r in collector_refs[:80]:
    print(f'{r["line"]}: {r["text"]}')
print("\n=== COLLECTOR SERVICE ===")
for line in unit:
    print(line)
PY

"$PY" -m py_compile "$ROOT/app/diagnose_current_universe_source.py"
"$PY" "$ROOT/app/diagnose_current_universe_source.py"

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true
echo
echo "PHASE0A_CURRENT_UNIVERSE_SOURCE_DIAGNOSIS=PASS"
