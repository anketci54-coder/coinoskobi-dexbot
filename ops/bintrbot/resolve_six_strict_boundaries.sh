#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_six_boundary_repair.$TS.bak"

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

patches={
  "HIGH_TRY":{
    "trading_start_local":"2024-06-05 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-high%C4%B1-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-43d0fcf86f0b45a5a8a89d82b5295bfb"
  },
  "IMX_TRY":{
    "trading_start_local":"2024-03-14 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-imxi-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-71b847d4bdbd455d8741fa59558ee953"
  },
  "JOE_TRY":{
    "trading_start_local":"2023-04-14 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/blog/Geli%C5%9Fmeler/cefb97cd3d564e1aaf7f6fe3f229be04"
  },
  "LEVER_TRY":{
    "trading_start_local":"2023-10-12 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/53c0ef7874954536989f5ab307e52d28"
  },
  "LOOM_TRY":{
    "trading_start_local":"2023-10-19 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-band-ve-loomu-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-c21003e5808e411688ec0133c16ceae2"
  },
  "LRC_TRY":{
    "membership_safe_lower_bound_local":"2026-03-18 23:59",
    "membership_safe_lower_bound_status":"VERIFIED_FIRST_PARTY_PRESENCE",
    "membership_safe_lower_bound_source_url":"https://www.binance.tr/tr/blog/Delisting/bf8cb9f3c3c4481789d7e459b642b445",
    "membership_from_semantics":"SAFE_LOWER_BOUND_NOT_LISTING_START",
    "membership_safe_lower_bound_note":"Binance TR first-party delisting announcement dated 2026-03-18 explicitly identifies LRC/TRY as an active trading pair scheduled to stop on 2026-04-01 06:00 Türkiye time. Exact original listing time remains unknown. End-of-announcement-day is used conservatively and is not a listing timestamp."
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
    print(sym, patch.get("trading_start_local") or patch.get("membership_safe_lower_bound_local"), patch["membership_from_semantics"])
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
for s in ["HIGH_TRY","IMX_TRY","JOE_TRY","LEVER_TRY","LOOM_TRY","LRC_TRY"]:
    print("\n"+s)
    for e in (cat.get("episode_windows") or {}).get(s,[]):
        print(e)
PY

echo
echo '========== BACKFILL QUICK CHECK =========='
"$ROOT/aggtrades-safe-status.sh" | sed -n '1,24p'
echo
"$ROOT/phase0-status.sh" | sed -n '1,24p'

echo
echo "SIX_STRICT_BOUNDARIES=PASS"
