#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_cos_dent_boundary.$TS.bak"

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
rows=x.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

patches={
  "COS_TRY":{
    "membership_safe_lower_bound_local":"2026-06-05 23:59",
    "membership_safe_lower_bound_status":"VERIFIED_FIRST_PARTY_PRESENCE",
    "membership_safe_lower_bound_source_url":"https://www.binance.tr/tr/blog/Delisting/26453546a2a0450999ae340fcfe3b790",
    "membership_from_semantics":"SAFE_LOWER_BOUND_NOT_LISTING_START",
    "membership_safe_lower_bound_note":"Binance TR first-party delisting announcement dated 2026-06-05 explicitly identifies COS/TRY as an active trading pair scheduled to stop on 2026-06-19. Exact original listing time remains unknown. End-of-announcement-day is used conservatively; it is not a listing timestamp."
  },
  "DENT_TRY":{
    "membership_safe_lower_bound_local":"2026-04-17 23:59",
    "membership_safe_lower_bound_status":"VERIFIED_FIRST_PARTY_PRESENCE",
    "membership_safe_lower_bound_source_url":"https://www.binance.tr/tr/blog/Delisting/b096854f246d4558b2033a05ad47d2ea",
    "membership_from_semantics":"SAFE_LOWER_BOUND_NOT_LISTING_START",
    "membership_safe_lower_bound_note":"Binance TR first-party delisting announcement dated 2026-04-17 explicitly identifies DENT/TRY as an active trading pair scheduled to stop on 2026-04-28. Exact original listing time remains unknown. End-of-announcement-day is used conservatively; it is not a listing timestamp."
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

print("COS_SAFE_LOWER_BOUND=2026-06-05 23:59 Europe/Istanbul")
print("DENT_SAFE_LOWER_BOUND=2026-04-17 23:59 Europe/Istanbul")
print("EXACT_LISTING_STARTS=UNKNOWN")
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
for s in ["COS_TRY","DENT_TRY"]:
    print("\n"+s)
    for e in (cat.get("episode_windows") or {}).get(s,[]):
        print(e)
PY

echo
echo '========== BACKFILLS =========='
"$ROOT/aggtrades-safe-status.sh" | sed -n '1,30p'
echo
"$ROOT/phase0-status.sh" | sed -n '1,24p'

echo
echo "COS_DENT_STRICT_BOUNDARIES=PASS"
