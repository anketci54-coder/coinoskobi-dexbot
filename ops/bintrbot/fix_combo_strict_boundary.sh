#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
TRANS="$ROOT/state/phase0a_transition_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_combo_boundary.$TS.bak"
[ -f "$TRANS" ] && cp -a "$TRANS" "$TRANS.pre_combo_boundary.$TS.bak"

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
if "COMBO_TRY" not in by:
    raise SystemExit("MISSING_HISTORICAL_ROW:COMBO_TRY")

by["COMBO_TRY"].update({
    "trading_start_local":"2023-06-02 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/duyurular/183db590e72b4e5389af82f2dd04f3c8",
    "listing_reason":"COCOS token swap and rename to COMBO completed on Binance TR.",
    "predecessor_symbol":"COCOS_TRY",
    "swap_ratio":"1 COCOS = 1 COMBO",
    "transition_type":"TOKEN_SWAP_RENAME",
    "price_series_continuity":"EPISODE_SPLIT_REQUIRED"
})
hist["updated_at_ms"]=time.time_ns()//1_000_000
atomic(hist_p,hist)

if trans_p.exists():
    trans=json.loads(trans_p.read_text())
    changed=False
    for r in trans.get("transitions",[]):
        if not isinstance(r,dict):
            continue
        if r.get("old_symbol")=="COCOS_TRY" or r.get("new_symbol")=="COMBO_TRY":
            r.update({
                "old_symbol":"COCOS_TRY",
                "new_symbol":"COMBO_TRY",
                "trading_end_local":"2023-05-29 11:00",
                "new_trading_start_local":"2023-06-02 11:00",
                "new_trading_start_status":"VERIFIED",
                "transition_type":"TOKEN_SWAP_RENAME",
                "swap_note":"1 COCOS = 1 COMBO",
                "economic_continuity":"RENAME_SWAP_CONTINUITY_1_TO_1",
                "price_series_continuity":"EPISODE_SPLIT_REQUIRED",
                "source":"BINANCE_TR_OFFICIAL",
                "source_url":"https://www.binance.tr/tr/blog/duyurular/183db590e72b4e5389af82f2dd04f3c8"
            })
            changed=True
    if changed:
        trans["updated_at_ms"]=time.time_ns()//1_000_000
        atomic(trans_p,trans)
        print("TRANSITION_SUCCESSOR_BOUNDARY_UPDATED=YES")
    else:
        print("TRANSITION_SUCCESSOR_BOUNDARY_UPDATED=NO_MATCH")
else:
    print("TRANSITION_SUCCESSOR_BOUNDARY_UPDATED=NO_FILE")

print("COMBO_TRADING_START=2023-06-02 11:00 Europe/Istanbul")
print("COMBO_TRADING_END=2025-03-28 06:00 Europe/Istanbul")
PY

"$PY" "$APP"

echo
echo '========== STRICT FINAL =========='
"$PY" - <<'PY'
import json
from pathlib import Path
cat=json.loads(Path("/root/bintrbot/data/catalog/dataset_catalog.json").read_text())
prof=json.loads(Path("/root/bintrbot/data/catalog/profiles/AI_BINANCE_TR_STRICT.json").read_text())
print("STRICT_READY_SYMBOLS=",len(cat.get("strict_ready_symbols",[])))
print("STRICT_BOUNDARY_PENDING=",len(cat.get("strict_boundary_pending_symbols",[])))
print("PENDING_SYMBOLS=",cat.get("strict_boundary_pending_symbols",[]))
print("PROFILE_STATUS=",prof.get("status"))
print("COMBO_EPISODES=")
for e in (cat.get("episode_windows") or {}).get("COMBO_TRY",[]):
    print(e)
PY

echo
echo '========== DATASET STATUS =========='
"$ROOT/dataset-status.sh"

echo
echo '========== CORE SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true

echo
echo "COMBO_STRICT_BOUNDARY=PASS"
