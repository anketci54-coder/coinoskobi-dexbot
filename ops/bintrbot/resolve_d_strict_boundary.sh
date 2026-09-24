#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
TRANS="$ROOT/state/phase0a_transition_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_d_boundary.$TS.bak"
[ -f "$TRANS" ] && cp -a "$TRANS" "$TRANS.pre_d_boundary.$TS.bak"

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
if "D_TRY" not in by:
    raise SystemExit("MISSING_HISTORICAL_ROW:D_TRY")

by["D_TRY"].update({
    "trading_start_local":"2025-01-09 11:00",
    "trading_start_status":"VERIFIED",
    "membership_from_semantics":"EXACT_LISTING_START",
    "listing_source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-mines-of-dalarnia-dar-token-takas%C4%B1n%C4%B1-ve-dar-open-network-d-olarak-yeniden-adland%C4%B1rma-plan%C4%B1n%C4%B1-destekleyecek-1127",
    "predecessor_symbol":"DAR_TRY",
    "swap_ratio":"1 DAR = 1 D",
    "transition_type":"TOKEN_SWAP_RENAME",
    "economic_continuity":"TOKEN_SWAP_RENAME_CONTINUITY_1_TO_1",
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
        if r.get("old_symbol")=="DAR_TRY" or r.get("new_symbol")=="D_TRY":
            r.update({
                "old_symbol":"DAR_TRY",
                "new_symbol":"D_TRY",
                "trading_end_local":"2025-01-06 06:00",
                "new_trading_start_local":"2025-01-09 11:00",
                "new_trading_start_status":"VERIFIED",
                "transition_type":"TOKEN_SWAP_RENAME",
                "swap_note":"1 DAR = 1 D",
                "economic_continuity":"TOKEN_SWAP_RENAME_CONTINUITY_1_TO_1",
                "price_series_continuity":"EPISODE_SPLIT_REQUIRED",
                "source":"BINANCE_TR_OFFICIAL",
                "source_url":"https://www.binance.tr/tr/blog/announcements/binance-tr-mines-of-dalarnia-dar-token-takas%C4%B1n%C4%B1-ve-dar-open-network-d-olarak-yeniden-adland%C4%B1rma-plan%C4%B1n%C4%B1-destekleyecek-1127"
            })
            changed=True
    if changed:
        trans["updated_at_ms"]=time.time_ns()//1_000_000
        atomic(trans_p,trans)
        print("DAR_D_TRANSITION_UPDATED=YES")
    else:
        print("DAR_D_TRANSITION_UPDATED=NO_MATCH")

print("D_TRADING_START=2025-01-09 11:00 Europe/Istanbul")
print("DAR_TRADING_END=2025-01-06 06:00 Europe/Istanbul")
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
print("D_TRY_EPISODES=")
for e in (cat.get("episode_windows") or {}).get("D_TRY",[]):
    print(e)
PY

echo
echo '========== LIVE / BACKFILL QUICK CHECK =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-aggtrades.service || true

echo
echo "D_STRICT_BOUNDARY=PASS"
