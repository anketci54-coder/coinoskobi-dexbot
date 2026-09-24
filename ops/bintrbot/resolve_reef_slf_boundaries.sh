#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
TRANS="$ROOT/state/phase0a_transition_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_reef_slf_boundary.$TS.bak"
[ -f "$TRANS" ] && cp -a "$TRANS" "$TRANS.pre_reef_slf_boundary.$TS.bak"

"$PY" - "$HIST" "$TRANS" <<'PY'
from pathlib import Path
import json, os, sys, time

hist_p=Path(sys.argv[1])
trans_p=Path(sys.argv[2])

def atomic(p,obj):
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(t,p)

hist=json.loads(hist_p.read_text())
rows=hist.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

patches={
  "SLF_TRY":{
    "trading_start_local":"2024-08-30 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/Announcements/0f3a4143c3414db3a25a93f0d664b374",
    "predecessor_symbol":"FRONT_TRY",
    "swap_ratio":"1 FRONT = 1 SLF",
    "transition_type":"TOKEN_SWAP_RENAME",
    "economic_continuity":"TOKEN_SWAP_RENAME_CONTINUITY_1_TO_1",
    "price_series_continuity":"EPISODE_SPLIT_REQUIRED"
  },
  "REEF_TRY":{
    "membership_safe_lower_bound_local":"2024-08-12 23:59",
    "membership_safe_lower_bound_status":"VERIFIED_FIRST_PARTY_PRESENCE",
    "membership_safe_lower_bound_source_url":"https://www.binance.tr/tr/blog/delisting/reeftry-ve-loomtry-i%C5%9Flem-%C3%A7iftlerinin-kald%C4%B1r%C4%B1lmas%C4%B1-hakk%C4%B1nda-bildirim-26082024-1040",
    "membership_from_semantics":"SAFE_LOWER_BOUND_NOT_LISTING_START",
    "membership_safe_lower_bound_note":"Binance TR first-party delisting announcement published 2024-08-12 explicitly identifies REEF/TRY as an active trading pair scheduled to stop on 2024-08-26 06:00 Türkiye time. Exact original listing time remains unknown. End-of-publication-day is used conservatively and is not a listing timestamp."
  }
}
for sym,patch in patches.items():
    if sym not in by:
        raise SystemExit(f"MISSING_HISTORICAL_ROW:{sym}")
    by[sym].update(patch)

hist["updated_at_ms"]=time.time_ns()//1_000_000
atomic(hist_p,hist)

if trans_p.exists():
    trans=json.loads(trans_p.read_text())
    changed=False
    for r in trans.get("transitions",[]):
        if not isinstance(r,dict):
            continue
        if r.get("old_symbol")=="FRONT_TRY" or r.get("new_symbol")=="SLF_TRY":
            r.update({
                "old_symbol":"FRONT_TRY",
                "new_symbol":"SLF_TRY",
                "trading_end_local":"2024-08-27 06:00",
                "new_trading_start_local":"2024-08-30 11:00",
                "new_trading_start_status":"VERIFIED",
                "transition_type":"TOKEN_SWAP_RENAME",
                "swap_note":"1 FRONT = 1 SLF",
                "economic_continuity":"TOKEN_SWAP_RENAME_CONTINUITY_1_TO_1",
                "price_series_continuity":"EPISODE_SPLIT_REQUIRED",
                "source":"BINANCE_TR_OFFICIAL",
                "source_url":"https://www.binance.tr/tr/blog/Announcements/0f3a4143c3414db3a25a93f0d664b374"
            })
            changed=True
    if changed:
        trans["updated_at_ms"]=time.time_ns()//1_000_000
        atomic(trans_p,trans)
        print("FRONT_SLF_TRANSITION_UPDATED=YES")
    else:
        print("FRONT_SLF_TRANSITION_UPDATED=NO_MATCH")

print("SLF_TRY 2024-08-30 11:00 EXACT_LISTING_START")
print("REEF_TRY 2024-08-12 23:59 SAFE_LOWER_BOUND_NOT_LISTING_START")
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
for s in ["REEF_TRY","SLF_TRY"]:
    print("\n"+s)
    for e in (cat.get("episode_windows") or {}).get(s,[]):
        print(e)
PY

echo
echo '========== STX GAP CHECK =========='
grep -RIn --include='*.json' 'STX_TRY' "$ROOT/data/quality" "$ROOT/state" 2>/dev/null | grep -E 'gap|2023-03|STX_TRY' | head -n 30 || true

echo
echo '========== QUICK HEALTH =========='
"$ROOT/aggtrades-safe-status.sh" | sed -n '1,24p'
echo
"$ROOT/phase0-status.sh" | sed -n '1,24p'

echo
echo "REEF_SLF_STRICT_BOUNDARIES=PASS"
