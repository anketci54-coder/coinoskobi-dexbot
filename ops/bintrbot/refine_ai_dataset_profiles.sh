#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
APP="$ROOT/app/build_ai_dataset_catalog.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$APP" "$ROOT/state/build_ai_dataset_catalog.py.pre_profile_refine.$TS.bak"

"$PY" - "$APP" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

# Current Binance TR membership is known at the dated snapshot. For strict use,
# only rows at/after that snapshot are eligible unless an earlier verified
# lifecycle start exists.
old='''    if symbol in current:
        return [{
            "source":"CURRENT_SNAPSHOT",
            "start_ms":None,
            "end_ms":None,
            "start_verified":False,
            "end_verified":False,
            "active_now_verified":True
        }]
'''
new='''    if symbol in current:
        snapshot_start = cur.get("snapshot_at_ms")
        return [{
            "source":"CURRENT_SNAPSHOT_SAFE_LOWER_BOUND",
            "start_ms":int(snapshot_start) if snapshot_start is not None else None,
            "end_ms":None,
            "start_verified":snapshot_start is not None,
            "end_verified":False,
            "active_now_verified":True,
            "historical_before_start_eligible":False,
            "note":"Current venue membership is verified at snapshot time only; earlier historical rows remain broad-only until listing start is independently verified."
        }]
'''
if old not in s:
    raise SystemExit("PATCH_ABORT current snapshot block missing")
s=s.replace(old,new,1)

old=''' "AI_BROAD_DISCOVERY":{
   "schema_version":1,
   "profile":"AI_BROAD_DISCOVERY",
   "status":"BUILDING",
'''
new=''' "AI_BROAD_DISCOVERY":{
   "schema_version":1,
   "profile":"AI_BROAD_DISCOVERY",
   "status":"READY_INCREMENTAL" if parts else "BUILDING",
'''
if old not in s:
    raise SystemExit("PATCH_ABORT broad profile missing")
s=s.replace(old,new,1)

old=''' "AI_BINANCE_TR_STRICT":{
   "schema_version":1,
   "profile":"AI_BINANCE_TR_STRICT",
   "status":"BUILDING",
'''
new=''' "AI_BINANCE_TR_STRICT":{
   "schema_version":1,
   "profile":"AI_BINANCE_TR_STRICT",
   "status":"READY_INCREMENTAL" if strict_ready_symbols else "BUILDING",
'''
s=s.replace(old,new,1)

old=''' "AI_EVENT_LIFECYCLE":{
   "schema_version":1,
   "profile":"AI_EVENT_LIFECYCLE",
   "status":"BUILDING",
'''
new=''' "AI_EVENT_LIFECYCLE":{
   "schema_version":1,
   "profile":"AI_EVENT_LIFECYCLE",
   "status":"READY_INCREMENTAL" if (delisted or transitions) else "BUILDING",
'''
s=s.replace(old,new,1)

# Add useful counts to every profile after the dict has been constructed.
needle='''for name,obj in profiles.items():
    atomic(PROFILES/f"{name}.json",obj)
'''
replacement='''profiles["AI_BROAD_DISCOVERY"].update({
   "catalogued_partitions":len(parts),
   "catalogued_symbols":len(symbols),
   "catalogued_rows":sum(p["row_count"] for p in parts),
   "coverage_is_incremental":True
})
profiles["AI_BINANCE_TR_STRICT"].update({
   "strict_ready_symbols":strict_ready_symbols,
   "strict_ready_symbol_count":len(strict_ready_symbols),
   "strict_boundary_pending_symbols":strict_boundary_pending,
   "strict_boundary_pending_count":len(strict_boundary_pending),
   "current_snapshot_safe_lower_bound_ms":cur.get("snapshot_at_ms"),
   "current_snapshot_safe_lower_bound_utc":cur.get("snapshot_at_utc"),
   "pre_snapshot_current_market_history":"BROAD_ONLY_UNTIL_LISTING_START_VERIFIED",
   "coverage_is_incremental":True
})
profiles["AI_EVENT_LIFECYCLE"].update({
   "verified_delisted_symbol_count":len(delisted),
   "verified_transition_symbol_count":len(transitions),
   "coverage_is_incremental":True
})
for name,obj in profiles.items():
    atomic(PROFILES/f"{name}.json",obj)
'''
if needle not in s:
    raise SystemExit("PATCH_ABORT profile write loop missing")
s=s.replace(needle,replacement,1)

p.write_text(s)
print("DATASET_PROFILE_REFINEMENT_PATCH=YES")
PY

"$PY" -m py_compile "$APP"
"$PY" "$APP"

echo
echo '========== PROFILE SUMMARY =========='
"$PY" - <<'PY'
import json
from pathlib import Path
base=Path("/root/bintrbot/data/catalog/profiles")
for name in ["AI_BROAD_DISCOVERY","AI_BINANCE_TR_STRICT","AI_EVENT_LIFECYCLE"]:
    x=json.loads((base/f"{name}.json").read_text())
    print(name)
    print("  STATUS=",x.get("status"))
    if name=="AI_BROAD_DISCOVERY":
        print("  ROWS=",x.get("catalogued_rows"))
        print("  SYMBOLS=",x.get("catalogued_symbols"))
        print("  PARTITIONS=",x.get("catalogued_partitions"))
    elif name=="AI_BINANCE_TR_STRICT":
        print("  STRICT_READY_SYMBOLS=",x.get("strict_ready_symbol_count"))
        print("  STRICT_BOUNDARY_PENDING=",x.get("strict_boundary_pending_count"))
        print("  SAFE_LOWER_BOUND=",x.get("current_snapshot_safe_lower_bound_utc"))
    else:
        print("  VERIFIED_DELISTED=",x.get("verified_delisted_symbol_count"))
        print("  VERIFIED_TRANSITIONS=",x.get("verified_transition_symbol_count"))
PY

echo
echo '========== CATALOG =========='
"$ROOT/dataset-status.sh"

echo
echo '========== CORE SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true

echo
echo "AI_DATASET_PROFILES_REFINED=PASS"
