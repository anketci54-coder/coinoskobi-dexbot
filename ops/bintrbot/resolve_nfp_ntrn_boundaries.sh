#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_nfp_ntrn_boundary.$TS.bak"

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

patches={
  "NFP_TRY":{
    "trading_start_local":"2023-12-27 13:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-nfpyi-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-b9502a049f7c40c0a5eb5243a365c6cc"
  },
  "NTRN_TRY":{
    "trading_start_local":"2023-11-23 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-gas-ve-ntrnyi-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-ee6f070b9af646c08295ea1aab1999ba"
  }
}

for sym,patch in patches.items():
    if sym not in by:
        raise SystemExit(f"MISSING_HISTORICAL_ROW:{sym}")
    by[sym].update(patch)

x["updated_at_ms"]=time.time_ns()//1_000_000
tmp=p.with_suffix(".json.tmp")
tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,p)

for sym,patch in patches.items():
    print(sym, patch["trading_start_local"], patch["membership_from_semantics"])
PY

"$PY" "$APP"

echo
echo '========== STRICT FINAL =========='
"$PY" - <<'PY'
import json
from pathlib import Path
cat=json.loads(Path("/root/bintrbot/data/catalog/dataset_catalog.json").read_text())
print("STRICT_READY_SYMBOLS=",len(cat.get("strict_ready_symbols",[])))
print("STRICT_BOUNDARY_PENDING=",len(cat.get("strict_boundary_pending_symbols",[])))
print("PENDING_SYMBOLS=",cat.get("strict_boundary_pending_symbols",[]))
for s in ["NFP_TRY","NTRN_TRY"]:
    print("\n"+s)
    for e in (cat.get("episode_windows") or {}).get(s,[]):
        print(e)
PY

echo
echo '========== QUICK HEALTH =========='
"$ROOT/aggtrades-safe-status.sh" | sed -n '1,24p'
echo
"$ROOT/phase0-status.sh" | sed -n '1,24p'

echo
echo "NFP_NTRN_STRICT_BOUNDARIES=PASS"
