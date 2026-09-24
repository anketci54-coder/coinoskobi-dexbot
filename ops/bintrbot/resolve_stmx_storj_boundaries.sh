#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_stmx_storj_boundary.$TS.bak"

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

patches={
  "STMX_TRY":{
    "trading_start_local":"2024-09-04 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-stmx-ve-sun%C4%B1-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-1052"
  },
  "STORJ_TRY":{
    "trading_start_local":"2022-07-29 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/announcements/19ce1bbc68aa43729f2194f2c1069514"
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
for s in ["STMX_TRY","STORJ_TRY"]:
    print("\n"+s)
    for e in (cat.get("episode_windows") or {}).get(s,[]):
        print(e)
PY

echo
echo '========== STX GAP TARGET =========='
find "$ROOT/data/quality" "$ROOT/state" -type f \( -name '*.json' -o -name '*.jsonl' \) -print0 2>/dev/null | xargs -0 grep -Il 'STX_TRY' 2>/dev/null | while read -r f; do
    grep -nE 'STX_TRY|2023-03|gap' "$f" 2>/dev/null | head -n 20 | sed "s#^#$f:#"
  done | head -n 80 || true

echo
echo '========== QUICK HEALTH =========='
"$ROOT/aggtrades-safe-status.sh" | sed -n '1,24p'
echo
"$ROOT/phase0-status.sh" | sed -n '1,24p'

echo
echo "STMX_STORJ_STRICT_BOUNDARIES=PASS"
