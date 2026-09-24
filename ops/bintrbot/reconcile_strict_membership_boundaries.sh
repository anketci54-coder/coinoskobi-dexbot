#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
APP="$ROOT/app/build_ai_dataset_catalog.py"
POLICY="$ROOT/state/dataset_collection_policy.json"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

cp -a "$HIST" "$HIST.pre_strict_boundaries.$TS.bak"
cp -a "$APP" "$ROOT/state/build_ai_dataset_catalog.py.pre_strict_boundaries.$TS.bak"
[ -f "$POLICY" ] && cp -a "$POLICY" "$POLICY.pre_strict_boundaries.$TS.bak"

"$PY" - "$HIST" "$POLICY" <<'PY'
from pathlib import Path
import json, os, sys, time

hist_p=Path(sys.argv[1])
policy_p=Path(sys.argv[2])

def atomic(p,obj):
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,p)

hist=json.loads(hist_p.read_text())
rows=hist.get("confirmed_delisted_try_seed",[])
by={r.get("symbol"):r for r in rows if isinstance(r,dict)}

exact = {
  "ACA_TRY": {
    "trading_start_local":"2023-07-20 11:00",
    "trading_start_status":"VERIFIED",
    "listing_source_url":"https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/bc9309d1ead04f7597d105c52beff09d"
  },
  "ACX_TRY": {
    "trading_start_local":"2024-12-11 11:00",
    "trading_start_status":"VERIFIED",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-acx-orca-ksm-ve-celoyu-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-1119"
  },
  "BAKE_TRY": {
    "trading_start_local":"2024-06-21 17:00",
    "trading_start_status":"VERIFIED",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-bakei-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-1010"
  },
  "BAND_TRY": {
    "trading_start_local":"2023-10-19 11:00",
    "trading_start_status":"VERIFIED",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-band-ve-loomu-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-c21003e5808e411688ec0133c16ceae2"
  },
  "BSW_TRY": {
    "trading_start_local":"2022-04-22 13:00",
    "trading_start_status":"VERIFIED",
    "listing_source_url":"https://www.binance.tr/tr/blog/geli%C5%9Fmeler/binance-tr-biswap%C4%B1-bsw-try-i%C5%9Flem-%C3%A7iftinde-listeleyecek-814788730d17440cbcb3579dcf373370"
  },
  "ACM_TRY": {
    "trading_start_local":"2023-08-10 11:00",
    "trading_start_status":"VERIFIED",
    "listing_source_url":"https://www.binance.tr/blog/Geli%C5%9Fmeler/f9891fe28bca49cf80c3916652e22588"
  }
}

for sym,patch in exact.items():
    if sym not in by:
        raise SystemExit(f"MISSING_HISTORICAL_ROW:{sym}")
    by[sym].update(patch)
    by[sym]["membership_from_semantics"]="EXACT_LISTING_START"

if "BTTC_TRY" not in by:
    raise SystemExit("MISSING_HISTORICAL_ROW:BTTC_TRY")
by["BTTC_TRY"].update({
    "trading_start_local": None,
    "trading_start_status":"UNKNOWN_EXACT_LISTING_START",
    "membership_safe_lower_bound_local":"2023-05-07 12:00",
    "membership_safe_lower_bound_status":"VERIFIED_FIRST_PARTY_PRESENCE",
    "membership_safe_lower_bound_source_url":"https://www.binance.tr/tr/blog/duyurular/ba458bf38cd04325a3e00645abdf2b2b",
    "membership_from_semantics":"SAFE_LOWER_BOUND_NOT_LISTING_START",
    "membership_safe_lower_bound_note":"Binance TR first-party announcement explicitly applies an order-function rule to BTTC/TRY at this time, proving the market existed no later than this timestamp. This is not claimed as the original listing time."
})

hist["strict_membership_boundary_policy"]="EXACT_LISTING_START_OR_FIRST_PARTY_SAFE_LOWER_BOUND"
hist["strict_membership_boundary_updated_at_ms"]=time.time_ns()//1_000_000
atomic(hist_p,hist)

if policy_p.exists():
    policy=json.loads(policy_p.read_text())
else:
    policy={"schema_version":1}
policy["strict_eligibility_rule"]="VERIFIED_MEMBERSHIP_FROM <= EVENT_TIME < VERIFIED_TRADING_END"
policy["verified_membership_from_semantics"]=[
    "EXACT_LISTING_START",
    "FIRST_PARTY_SAFE_LOWER_BOUND_NOT_LISTING_START",
    "CURRENT_MEMBERSHIP_SNAPSHOT_SAFE_LOWER_BOUND"
]
policy["safe_lower_bound_rule"]="A conservative first-party proof-of-presence time may open strict eligibility only from that time forward; it must never be relabeled as the original listing start."
policy["unknown_boundary_policy"]="EXCLUDE_FROM_STRICT_KEEP_IN_BROAD"
policy["updated_at_ms"]=time.time_ns()//1_000_000
atomic(policy_p,policy)

print("EXACT_LISTING_STARTS_UPDATED=",",".join(sorted(exact)))
print("BTTC_SAFE_LOWER_BOUND=2023-05-07 12:00 Europe/Istanbul")
PY

"$PY" - "$APP" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

start=s.index("def boundaries(symbol):")
end=s.index("\nparts=[]", start)

new_func='''def boundaries(symbol):
    out=[]

    # 1) Canonical lifecycle episodes, when available.
    for e in episodes.get(symbol,[]):
        out.append({
            "source":"LIFECYCLE_REGISTRY",
            "start_ms":e.get("trading_start_ms"),
            "end_ms":e.get("trading_end_ms"),
            "start_verified":bool(e.get("start_boundary_verified")),
            "end_verified":bool(e.get("end_boundary_verified")),
            "episode_ordinal":e.get("episode_ordinal"),
            "canonical_asset_key":e.get("canonical_asset_key"),
            "membership_from_semantics":"EXACT_EPISODE_BOUNDARY" if e.get("start_boundary_verified") else "UNKNOWN"
        })

    # 2) Transition evidence. Do not suppress other episodes for the same ticker.
    if symbol in transitions:
        r=transitions[symbol]
        st=tr_ms(r.get("old_trading_start_local"))
        en=tr_ms(r.get("trading_end_local"))
        out.append({
            "source":"TRANSITION_REGISTRY",
            "start_ms":st,
            "end_ms":en,
            "start_verified":r.get("old_trading_start_status")=="VERIFIED",
            "end_verified":en is not None,
            "membership_from_semantics":"EXACT_LISTING_START" if r.get("old_trading_start_status")=="VERIFIED" else "UNKNOWN"
        })

    # 3) Delisted-market evidence: exact listing start where known, otherwise a
    # conservative first-party proof-of-presence lower bound.
    if symbol in delisted:
        r=delisted[symbol]
        exact=tr_ms(r.get("trading_start_local"))
        safe=tr_ms(r.get("membership_safe_lower_bound_local"))
        en=tr_ms(r.get("delisted_local"))
        if r.get("trading_start_status")=="VERIFIED" and exact is not None:
            st=exact
            verified=True
            semantics="EXACT_LISTING_START"
        elif r.get("membership_safe_lower_bound_status")=="VERIFIED_FIRST_PARTY_PRESENCE" and safe is not None:
            st=safe
            verified=True
            semantics="FIRST_PARTY_SAFE_LOWER_BOUND_NOT_LISTING_START"
        else:
            st=exact
            verified=False
            semantics="UNKNOWN"
        out.append({
            "source":"DELIST_REGISTRY",
            "start_ms":st,
            "end_ms":en,
            "start_verified":verified,
            "end_verified":en is not None,
            "membership_from_semantics":semantics
        })

    # 4) Current official snapshot is itself a verified proof that the market is
    # active from the snapshot timestamp onward. Earlier history remains broad
    # unless separately verified above.
    if symbol in current:
        snapshot_start=cur.get("snapshot_at_ms")
        out.append({
            "source":"CURRENT_SNAPSHOT_SAFE_LOWER_BOUND",
            "start_ms":int(snapshot_start) if snapshot_start is not None else None,
            "end_ms":None,
            "start_verified":snapshot_start is not None,
            "end_verified":False,
            "active_now_verified":True,
            "historical_before_start_eligible":False,
            "membership_from_semantics":"CURRENT_MEMBERSHIP_SNAPSHOT_SAFE_LOWER_BOUND",
            "note":"Current venue membership is verified at snapshot time only; earlier historical rows remain broad-only until separately verified."
        })

    # Deduplicate identical windows while preserving distinct episode semantics.
    seen=set()
    dedup=[]
    for e in out:
        key=(e.get("source"),e.get("start_ms"),e.get("end_ms"),e.get("episode_ordinal"),e.get("membership_from_semantics"))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(e)
    return dedup
'''

s=s[:start]+new_func+s[end:]

s=s.replace(
    '"eligibility":"VERIFIED_LISTING_START <= EVENT_TIME < VERIFIED_TRADING_END; active episode requires verified start",',
    '"eligibility":"VERIFIED_MEMBERSHIP_FROM <= EVENT_TIME < VERIFIED_TRADING_END; membership-from may be exact listing start or an explicitly labeled first-party/current-snapshot safe lower bound",'
)

p.write_text(s)
print("CATALOG_BOUNDARY_MERGE_PATCH=YES")
PY

"$PY" -m py_compile "$APP"
"$PY" "$APP"

echo
echo '========== STRICT BOUNDARY RESULT =========='
"$PY" - <<'PY'
import json
from pathlib import Path
cat=json.loads(Path("/root/bintrbot/data/catalog/dataset_catalog.json").read_text())
profile=json.loads(Path("/root/bintrbot/data/catalog/profiles/AI_BINANCE_TR_STRICT.json").read_text())

print("STRICT_READY_SYMBOLS=",len(cat.get("strict_ready_symbols",[])))
print("STRICT_BOUNDARY_PENDING=",len(cat.get("strict_boundary_pending_symbols",[])))
print("PENDING_SYMBOLS=",cat.get("strict_boundary_pending_symbols",[]))
print("PROFILE_STATUS=",profile.get("status"))

for s in ["ACA_TRY","ACM_TRY","ACX_TRY","BAKE_TRY","BAND_TRY","BSW_TRY","BTTC_TRY","LUNA_TRY"]:
    print("\n",s)
    for e in (cat.get("episode_windows") or {}).get(s,[]):
        print(" ",e)
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
echo "STRICT_BOUNDARIES_RECONCILED=PASS"
