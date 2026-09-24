#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_mbox_move_mtl_boundary.$TS.bak"

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

patches={
  "MOVE_TRY":{
    "trading_start_local":"2024-12-09 15:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/b456ef0f19994a4e9f3ddec46d4249b1"
  },
  "MTL_TRY":{
    "trading_start_local":"2023-09-21 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/blog/Geli%C5%9Fmeler/914d83b6d28e4db2ad6ece9c665c5536"
  },
  "MBOX_TRY":{
    "membership_safe_lower_bound_local":"2024-10-24 23:59",
    "membership_safe_lower_bound_status":"VERIFIED_FIRST_PARTY_PRESENCE",
    "membership_safe_lower_bound_source_url":"https://www.binance.tr/tr/blog/announcements/fiyat-ad%C4%B1m%C4%B1-d%C3%BCzenlemesi-hakk%C4%B1nda-duyuru-04112024-1090",
    "membership_from_semantics":"SAFE_LOWER_BOUND_NOT_LISTING_START",
    "membership_safe_lower_bound_note":"Binance TR first-party announcement published 2024-10-24 explicitly lists MBOX/TRY among active trading pairs whose tick size would be adjusted on 2024-11-04. Exact original listing time remains unknown. End-of-publication-day is used conservatively and must not be treated as the listing timestamp."
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
for s in ["MBOX_TRY","MOVE_TRY","MTL_TRY"]:
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
echo "MBOX_MOVE_MTL_STRICT_BOUNDARIES=PASS"
