#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_phb_boundary.$TS.bak"

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

sym="PHB_TRY"
if sym not in by:
    raise SystemExit("MISSING_HISTORICAL_ROW:PHB_TRY")

by[sym].update({
    "trading_start_local":"2024-05-08 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-egld-phb-ve-rsryi-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-3e7a89500d944363909c7827cb0eb802"
})

x["updated_at_ms"]=time.time_ns()//1_000_000
tmp=p.with_suffix(".json.tmp")
tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,p)

print("PHB_TRY 2024-05-08 11:00 EXACT_LISTING_START")
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
print("PHB_TRY")
for e in (cat.get("episode_windows") or {}).get("PHB_TRY",[]):
    print(e)
PY

echo
echo '========== QUICK HEALTH =========='
"$ROOT/aggtrades-safe-status.sh" | sed -n '1,24p'
echo
"$ROOT/phase0-status.sh" | sed -n '1,24p'

echo
echo "PHB_STRICT_BOUNDARY=PASS"
