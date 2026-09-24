#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p   "$ROOT/data/catalog/profiles"   "$ROOT/data/bronze/binance_me_type1_superset/klines_1m"   "$ROOT/data/silver"   "$ROOT/data/gold/training"   "$ROOT/state"

[ -f "$ROOT/app/phase0_gate.py" ] &&   cp -a "$ROOT/app/phase0_gate.py" "$ROOT/state/phase0_gate.py.pre_ai_dataset_policy.$TS.bak"

cat > "$ROOT/state/dataset_collection_policy.json" <<'JSON'
{
  "schema_version": 1,
  "status": "ENFORCED",
  "primary_goal": "AI_TRAINING_DATA_COLLECTION",
  "physical_storage_policy": "ONE_RAW_BRONZE_LAKE_PLUS_LOGICAL_DATASET_INDEXES",
  "collection_policy": "COLLECT_BROADLY_LABEL_EXPLICITLY_FILTER_AT_USE_TIME",
  "bronze": {
    "purpose": "Maximum recoverable raw market data with provenance",
    "uncertain_venue_data_allowed": true,
    "uncertain_data_blocks_collection": false,
    "silent_deletion": false,
    "forward_fill": false
  },
  "dataset_profiles": {
    "AI_BROAD_DISCOVERY": {
      "venue_uncertain_allowed": true,
      "purpose": "pattern discovery / representation learning / research",
      "execution_claims_allowed": false
    },
    "AI_BINANCE_TR_STRICT": {
      "venue_uncertain_allowed": false,
      "purpose": "Binance TR strategy training / replay / backtest",
      "requires_verified_membership_window": true
    },
    "AI_EVENT_LIFECYCLE": {
      "purpose": "listing / delisting / rename / swap / redenomination / merger research",
      "requires_event_and_transition_labels": true
    }
  },
  "phase0_rule": "Uncertain venue membership is informational and does not independently block Phase 0. Historical coverage and integrity still matter.",
  "strict_eligibility_rule": "VERIFIED_LISTING_START <= EVENT_TIME < VERIFIED_TRADING_END",
  "unknown_boundary_policy": "EXCLUDE_FROM_STRICT_KEEP_IN_BROAD",
  "forbidden_inferences": [
    "KLINE_ACCESSIBLE => BINANCE_TR_LISTED",
    "FIRST_KLINE => BINANCE_TR_LISTING_START",
    "LAST_KLINE => BINANCE_TR_DELIST_TIME"
  ]
}
JSON

# Remove the accidentally blocking candidate-evidence gate while preserving it as INFO.
"$PY" - "$ROOT/app/phase0_gate.py" <<'PY'
from pathlib import Path
import re, sys

p=Path(sys.argv[1])
s=p.read_text()

pattern=r'''add\(
    "0A_MEMBERSHIP_EVIDENCE",
    candidate0\.get\("status"\) == "COMPLETE"
    and len\(candidate0\.get\("pending_candidates"\) or \{\}\) == 0,
    f'status=\{candidate0\.get\("status"\)\} pending_candidates=\{len\(candidate0\.get\("pending_candidates"\) or \{\}\)\}'
\)

'''
s2,n=re.subn(pattern,"",s,count=1)
if n==0 and '"0A_MEMBERSHIP_EVIDENCE"' in s:
    raise SystemExit("PATCH_ABORT unexpected membership gate shape")
s=s2

marker='''for name, ok, detail in checks:
    print(f'{"PASS" if ok else "PENDING"} {name} :: {detail}')
'''
info='''for name, ok, detail in checks:
    print(f'{"PASS" if ok else "PENDING"} {name} :: {detail}')

print(
    "INFO 0A_MEMBERSHIP_EVIDENCE :: "
    f'status={candidate0.get("status")} '
    f'pending_candidates={len(candidate0.get("pending_candidates") or {})} '
    "non_blocking=true broad_raw_collection_allowed=true"
)
'''
if "INFO 0A_MEMBERSHIP_EVIDENCE ::" not in s:
    if marker not in s:
        raise SystemExit("PATCH_ABORT output marker missing")
    s=s.replace(marker,info,1)

p.write_text(s)
print("PHASE0_MEMBERSHIP_BLOCKER_REMOVED=YES")
PY

cat > "$ROOT/app/build_ai_dataset_catalog.py" <<'PY'
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path("/root/bintrbot")
CANON=ROOT/"data/bronze/klines_1m"
SUPERSET=ROOT/"data/bronze/binance_me_type1_superset/klines_1m"
CURRENT=ROOT/"data/meta/identity/current_try_core.json"
HIST=ROOT/"state/phase0a_historical_universe.json"
TRANS=ROOT/"state/phase0a_transition_universe.json"
EVID=ROOT/"state/phase0a_candidate_membership_evidence.json"
DB=ROOT/"data/meta/identity/registry.sqlite3"
OUT=ROOT/"data/catalog/dataset_catalog.json"
PROFILES=ROOT/"data/catalog/profiles"

def load(p,default):
    try:return json.loads(p.read_text())
    except Exception:return default

def atomic(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(tmp,p)

def tr_ms(s):
    if not s:return None
    try:
        dt=datetime.strptime(s,"%Y-%m-%d %H:%M").replace(
            tzinfo=timezone(timedelta(hours=3))
        )
        return int(dt.astimezone(timezone.utc).timestamp()*1000)
    except Exception:
        return None

cur=load(CURRENT,{})
current={m.get("symbol") for m in cur.get("markets",[]) if m.get("symbol")}

hist=load(HIST,{})
delisted={
    r.get("symbol"):r for r in hist.get("confirmed_delisted_try_seed",[])
    if isinstance(r,dict) and r.get("symbol")
}

trans=load(TRANS,{})
transitions={
    r.get("old_symbol"):r for r in trans.get("transitions",[])
    if isinstance(r,dict) and r.get("old_symbol")
}

evid=load(EVID,{})
pending=set((evid.get("pending_candidates") or {}).keys())

episodes={}
if DB.exists():
    try:
        con=sqlite3.connect(DB)
        con.row_factory=sqlite3.Row
        exists=con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_lifecycle_episodes'"
        ).fetchone()
        if exists:
            for r in con.execute("""
                SELECT symbol,episode_ordinal,canonical_asset_key,
                       trading_start_ms,trading_end_ms,episode_status,
                       start_boundary_verified,end_boundary_verified
                FROM market_lifecycle_episodes
                ORDER BY symbol,episode_ordinal
            """):
                episodes.setdefault(r["symbol"],[]).append(dict(r))
        con.close()
    except Exception:
        pass

def classify(symbol, physical_scope):
    if physical_scope=="SOURCE_SUPERSET":
        return "VENUE_UNCERTAIN_CANDIDATE"
    if symbol in transitions:
        return "BINANCE_TR_VERIFIED_TRANSITION_MEMBER"
    if symbol in delisted:
        return "BINANCE_TR_VERIFIED_DELISTED_MEMBER"
    if symbol in current:
        return "BINANCE_TR_CURRENT_MEMBER"
    return "SOURCE_SUPERSET_UNCLASSIFIED"

def boundaries(symbol):
    out=[]
    for e in episodes.get(symbol,[]):
        out.append({
            "source":"LIFECYCLE_REGISTRY",
            "start_ms":e.get("trading_start_ms"),
            "end_ms":e.get("trading_end_ms"),
            "start_verified":bool(e.get("start_boundary_verified")),
            "end_verified":bool(e.get("end_boundary_verified")),
            "episode_ordinal":e.get("episode_ordinal"),
            "canonical_asset_key":e.get("canonical_asset_key")
        })
    if out:
        return out

    if symbol in transitions:
        r=transitions[symbol]
        start=tr_ms(r.get("old_trading_start_local"))
        end=tr_ms(r.get("trading_end_local"))
        return [{
            "source":"TRANSITION_REGISTRY",
            "start_ms":start,
            "end_ms":end,
            "start_verified":r.get("old_trading_start_status")=="VERIFIED",
            "end_verified":end is not None
        }]
    if symbol in delisted:
        r=delisted[symbol]
        start=tr_ms(r.get("trading_start_local"))
        end=tr_ms(r.get("delisted_local"))
        return [{
            "source":"DELIST_REGISTRY",
            "start_ms":start,
            "end_ms":end,
            "start_verified":r.get("trading_start_status")=="VERIFIED",
            "end_verified":end is not None
        }]
    if symbol in current:
        return [{
            "source":"CURRENT_SNAPSHOT",
            "start_ms":None,
            "end_ms":None,
            "start_verified":False,
            "end_verified":False,
            "active_now_verified":True
        }]
    return []

parts=[]
for base,scope in ((CANON,"CANONICAL_RAW"),(SUPERSET,"SOURCE_SUPERSET")):
    if not base.exists():
        continue
    for mp in base.glob("symbol=*/year=*/month=*/manifest.json"):
        try:
            m=json.loads(mp.read_text())
        except Exception:
            continue
        symbol=m.get("symbol") or mp.parts[-4].split("=",1)[-1]
        parts.append({
            "symbol":symbol,
            "year_month":m.get("year_month") or (
                mp.parts[-3].split("=",1)[-1]+"-"+mp.parts[-2].split("=",1)[-1]
            ),
            "physical_scope":scope,
            "membership_class":classify(symbol,scope),
            "manifest_status":m.get("status"),
            "row_count":int(m.get("row_count") or 0),
            "gap_count":int(m.get("gap_count") or 0),
            "sha256":m.get("sha256"),
            "manifest_path":str(mp.relative_to(ROOT)),
            "source":m.get("source"),
            "universe_scope":m.get("universe_scope"),
        })

parts.sort(key=lambda x:(x["symbol"],x["year_month"],x["physical_scope"]))

symbols=sorted(set(p["symbol"] for p in parts))
classes={}
for p in parts:
    classes[p["membership_class"]]=classes.get(p["membership_class"],0)+1

episode_index={s:boundaries(s) for s in symbols}
strict_ready_symbols=[]
strict_boundary_pending=[]
for s in symbols:
    eps=episode_index.get(s) or []
    if any(e.get("start_verified") and (e.get("end_verified") or e.get("active_now_verified")) for e in eps):
        strict_ready_symbols.append(s)
    else:
        strict_boundary_pending.append(s)

catalog={
    "schema_version":1,
    "catalog_version":f"CAT-{int(time.time())}",
    "built_at_ms":time.time_ns()//1_000_000,
    "storage_policy":"ONE_RAW_BRONZE_LAKE_PLUS_LOGICAL_INDEXES",
    "physical_partition_count":len(parts),
    "symbol_count":len(symbols),
    "rows_catalogued":sum(p["row_count"] for p in parts),
    "membership_class_partition_counts":classes,
    "current_snapshot_markets":len(current),
    "confirmed_delisted_markets":len(delisted),
    "confirmed_transition_markets":len(transitions),
    "uncertain_candidates":sorted(pending),
    "strict_ready_symbols":strict_ready_symbols,
    "strict_boundary_pending_symbols":strict_boundary_pending,
    "episode_windows":episode_index,
    "partitions":parts
}
atomic(OUT,catalog)

profiles={
 "AI_BROAD_DISCOVERY":{
   "schema_version":1,
   "profile":"AI_BROAD_DISCOVERY",
   "status":"BUILDING",
   "source_catalog":str(OUT),
   "include_membership_classes":[
      "BINANCE_TR_CURRENT_MEMBER",
      "BINANCE_TR_VERIFIED_DELISTED_MEMBER",
      "BINANCE_TR_VERIFIED_TRANSITION_MEMBER",
      "VENUE_UNCERTAIN_CANDIDATE",
      "SOURCE_SUPERSET_UNCLASSIFIED"
   ],
   "quality_rule":"manifest_status=COMPLETE; retain gap flags; no silent fill",
   "venue_membership_feature_required":True,
   "execution_claims_allowed":False,
   "split_policy":"TIME_ORDERED_TRAIN_VALIDATION_FINAL_TEST_AFTER_COVERAGE_FREEZE"
 },
 "AI_BINANCE_TR_STRICT":{
   "schema_version":1,
   "profile":"AI_BINANCE_TR_STRICT",
   "status":"BUILDING",
   "source_catalog":str(OUT),
   "allowed_membership_classes":[
      "BINANCE_TR_CURRENT_MEMBER",
      "BINANCE_TR_VERIFIED_DELISTED_MEMBER",
      "BINANCE_TR_VERIFIED_TRANSITION_MEMBER"
   ],
   "row_filter":"verified episode membership mask",
   "eligibility":"VERIFIED_LISTING_START <= EVENT_TIME < VERIFIED_TRADING_END; active episode requires verified start",
   "unknown_boundary":"EXCLUDE",
   "venue_uncertain":"EXCLUDE",
   "split_policy":"TIME_ORDERED_TRAIN_VALIDATION_FINAL_TEST; FINAL_TEST_UNTOUCHED"
 },
 "AI_EVENT_LIFECYCLE":{
   "schema_version":1,
   "profile":"AI_EVENT_LIFECYCLE",
   "status":"BUILDING",
   "source_catalog":str(OUT),
   "symbols":"delisted and transition registries",
   "required_labels":[
      "EVENT_TIME","KNOWN_AT","TRANSITION_TYPE","REASON","MECHANISM",
      "SWAP_RATIO","ECONOMIC_CONTINUITY","PRICE_SERIES_CONTINUITY"
   ],
   "ticker_continuity_is_asset_continuity":False,
   "split_policy":"TIME_ORDERED_EVENT_SPLIT_AFTER_EVENT_REGISTRY_FREEZE"
 }
}
for name,obj in profiles.items():
    atomic(PROFILES/f"{name}.json",obj)

print(json.dumps({
    "CATALOG_STATUS":"PASS",
    "PARTITIONS":len(parts),
    "SYMBOLS":len(symbols),
    "ROWS_CATALOGUED":catalog["rows_catalogued"],
    "MEMBERSHIP_CLASSES":classes,
    "STRICT_READY_SYMBOLS":len(strict_ready_symbols),
    "STRICT_BOUNDARY_PENDING":len(strict_boundary_pending),
    "DATASET_PROFILES":list(profiles),
},ensure_ascii=False,indent=2))
PY

cat > "$ROOT/app/backfill_uncertain_candidate_klines.py" <<'PY'
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path("/root/bintrbot")
DISC=ROOT/"state/phase0a_unknown_historical_try_discovery.json"
CURR=ROOT/"state/phase0a_unknown_try_currentness.json"
MAIN=ROOT/"state/backfill_klines.json"
DELISTED=ROOT/"state/delisted_historical_coverage.json"
TRANS=ROOT/"state/backfill_transition_klines.json"
OUT=ROOT/"data/bronze/binance_me_type1_superset/klines_1m"
STATE=ROOT/"state/backfill_uncertain_candidates.json"
URL="https://api.binance.me/api/v1/klines"
TARGETS={"BTT_TRY","FIS_TRY","ZAMA_TRY","币安人生_TRY"}
REQ_GAP=0.85
MIN_FREE=20*1024**3

SCHEMA=pa.schema([
 ("symbol",pa.string()),("symbol_type",pa.int8()),("open_time_ms",pa.int64()),
 ("open",pa.string()),("high",pa.string()),("low",pa.string()),("close",pa.string()),
 ("volume",pa.string()),("close_time_ms",pa.int64()),("quote_volume",pa.string()),
 ("trade_count",pa.int64()),("taker_buy_base_volume",pa.string()),
 ("taker_buy_quote_volume",pa.string()),("ignore",pa.string())
])

def load(p,d):
    try:return json.loads(p.read_text())
    except Exception:return d

def atomic(p,o):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(t,p)

def month(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).strftime("%Y-%m")
def nextm(ym):
    y,m=map(int,ym.split("-"))
    return f"{y+1:04d}-01" if m==12 else f"{y:04d}-{m+1:02d}"
def months(a,b):
    x=a
    while True:
        yield x
        if x==b:return
        x=nextm(x)
def bounds(ym):
    y,m=map(int,ym.split("-"))
    a=datetime(y,m,1,tzinfo=timezone.utc)
    b=datetime(y+(m==12),1 if m==12 else m+1,1,tzinfo=timezone.utc)
    return int(a.timestamp()*1000),int(b.timestamp()*1000)-1
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def mpath(s,ym):
    y,m=ym.split("-")
    return OUT/f"symbol={s}"/f"year={y}"/f"month={m}"/"manifest.json"
def done(s,ym):
    p=mpath(s,ym)
    try:return json.loads(p.read_text()).get("status")=="COMPLETE"
    except Exception:return False

async def get(session,params):
    last=None
    for n in range(8):
        if shutil.disk_usage("/").free<MIN_FREE:raise RuntimeError("DISK_GUARD_STOP")
        try:
            async with session.get(URL,params=params,timeout=aiohttp.ClientTimeout(total=30)) as r:
                text=await r.text()
                if r.status==200:
                    x=json.loads(text); return x.get("data",x) if isinstance(x,dict) else x
                last=f"HTTP_{r.status}:{text[:160]}"
                if r.status in (418,429) or r.status>=500:
                    await asyncio.sleep(min(2**n,30));continue
                raise RuntimeError(last)
        except (aiohttp.ClientError,asyncio.TimeoutError) as e:
            last=repr(e);await asyncio.sleep(min(2**n,30))
        finally:
            await asyncio.sleep(REQ_GAP)
    raise RuntimeError(f"RETRY_EXHAUSTED:{last}")

async def fetch(session,sym,ym,first,last):
    a,b=bounds(ym); start=max(a,first); end=min(b,last)
    rows=[]; cur=start; api=sym.replace("_","")
    while cur<=end:
        d=await get(session,{"symbol":api,"interval":"1m","startTime":cur,"endTime":end,"limit":1000})
        batch=[r for r in d if isinstance(r,list) and len(r)>=11] if isinstance(d,list) else []
        if not batch:break
        rows.extend(batch)
        nxt=int(batch[-1][0])+60000
        if nxt<=cur:raise RuntimeError(f"NON_ADVANCING:{sym}:{ym}")
        cur=nxt
        if len(batch)<1000:break
    return rows,start,end

def write(sym,ym,rows,start,end):
    y,m=ym.split("-"); folder=OUT/f"symbol={sym}"/f"year={y}"/f"month={m}"
    folder.mkdir(parents=True,exist_ok=True)
    fp=folder/"klines.parquet"; mp=folder/"manifest.json"
    seen=set(); data=[]; gaps=0; largest=0; prev=None; dup=0
    for r in sorted(rows,key=lambda z:int(z[0])):
        ot=int(r[0])
        if ot in seen:dup+=1;continue
        seen.add(ot)
        if prev is not None and ot-prev>60000:
            gaps+=1;largest=max(largest,(ot-prev)//60000-1)
        prev=ot
        data.append({
          "symbol":sym,"symbol_type":1,"open_time_ms":ot,
          "open":str(r[1]),"high":str(r[2]),"low":str(r[3]),"close":str(r[4]),
          "volume":str(r[5]),"close_time_ms":int(r[6]),"quote_volume":str(r[7]),
          "trade_count":int(r[8]),"taker_buy_base_volume":str(r[9]),
          "taker_buy_quote_volume":str(r[10]),"ignore":str(r[11]) if len(r)>11 else ""
        })
    checksum=None
    if data:
        tmp=folder/"klines.parquet.tmp"
        pq.write_table(pa.Table.from_pylist(data,schema=SCHEMA),tmp,compression="zstd",compression_level=6)
        os.replace(tmp,fp);checksum=sha(fp)
    info={
      "status":"COMPLETE","symbol":sym,"year_month":ym,"row_count":len(data),
      "duplicate_count_removed":dup,"gap_count":gaps,"largest_gap_minutes":largest,
      "first_open_time_ms":data[0]["open_time_ms"] if data else None,
      "last_open_time_ms":data[-1]["open_time_ms"] if data else None,
      "requested_start_ms":start,"requested_end_ms":end,"sha256":checksum,
      "source":URL,"source_scope":"BINANCE_ME_TYPE1_SUPERSET",
      "venue_membership_class":"UNCERTAIN","canonical_binance_tr_membership":False,
      "training_default":"AI_BROAD_DISCOVERY_ONLY",
      "completed_at_ms":time.time_ns()//1_000_000
    }
    atomic(mp,info);return info

async def main():
    main=load(MAIN,{})
    cov=load(DELISTED,{})
    trans=load(TRANS,{})
    if main.get("status")!="COMPLETE" or cov.get("status")!="PASS" or trans.get("status")!="COMPLETE":
        out={
          "schema_version":1,"status":"WAITING_ON_HISTORICAL_DEPENDENCIES",
          "main_status":main.get("status"),"main_jobs_remaining":main.get("jobs_remaining"),
          "delisted_coverage":cov.get("status"),
          "transition_status":trans.get("status"),"transition_jobs_remaining":trans.get("jobs_remaining"),
          "backfill_started":False,"updated_at_ms":time.time_ns()//1_000_000
        }
        atomic(STATE,out);print(json.dumps(out,ensure_ascii=False,indent=2));return

    disc=load(DISC,{})
    curr=load(CURR,{})
    first={r["symbol"]:r.get("first_open_time_ms") for r in disc.get("found",[]) if r.get("symbol") in TARGETS}
    last={r["symbol"]:r.get("latest_open_time_ms") for r in curr.get("rows",[]) if r.get("symbol") in TARGETS}
    targets=[]
    for s in sorted(TARGETS):
        if first.get(s) is not None and last.get(s) is not None:
            targets.append((s,int(first[s]),int(last[s])))
    jobs=[]
    for s,a,b in targets:
        for ym in months(month(a),month(b)):
            if not done(s,ym):jobs.append((s,ym,a,b))
    state={
      "schema_version":1,"status":"RUNNING","targets_total":len(targets),
      "jobs_remaining_at_start":len(jobs),"jobs_remaining":len(jobs),
      "months_complete_this_run":0,"rows_written_this_run":0,"errors":{},
      "source_scope":"BINANCE_ME_TYPE1_SUPERSET","venue_membership_class":"UNCERTAIN",
      "backfill_started":True,"updated_at_ms":time.time_ns()//1_000_000
    }
    atomic(STATE,state)
    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-uncertain-candidate-backfill/1.0"}) as session:
        for i,(s,ym,a,b) in enumerate(jobs,1):
            try:
                rows,st,en=await fetch(session,s,ym,a,b)
                info=write(s,ym,rows,st,en)
                state["months_complete_this_run"]+=1
                state["rows_written_this_run"]+=info["row_count"]
                state["jobs_remaining"]=len(jobs)-i
                state["last_symbol"]=s;state["last_month"]=ym
                state["updated_at_ms"]=time.time_ns()//1_000_000
                atomic(STATE,state)
                print("UNCERTAIN_MONTH_OK",s,ym,"rows=",info["row_count"],flush=True)
            except Exception as e:
                state["errors"][f"{s}:{ym}"]=repr(e);state["status"]="FAILED"
                state["updated_at_ms"]=time.time_ns()//1_000_000;atomic(STATE,state);raise
    state["status"]="COMPLETE";state["jobs_remaining"]=0
    state["completed_at_ms"]=time.time_ns()//1_000_000;atomic(STATE,state)
    print("UNCERTAIN_CANDIDATE_BACKFILL_COMPLETE",flush=True)

asyncio.run(main())
PY

cat > /etc/systemd/system/bintrbot-dataset-catalog.service <<'UNIT'
[Unit]
Description=BintrBot AI Dataset Catalog Builder
After=local-fs.target

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/build_ai_dataset_catalog.py
User=root
Nice=19
IOSchedulingClass=idle
UNIT

cat > /etc/systemd/system/bintrbot-dataset-catalog.timer <<'UNIT'
[Unit]
Description=Refresh BintrBot AI Dataset Catalog

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
AccuracySec=1min
Persistent=true
Unit=bintrbot-dataset-catalog.service

[Install]
WantedBy=timers.target
UNIT

cat > /etc/systemd/system/bintrbot-backfill-uncertain-candidates.service <<'UNIT'
[Unit]
Description=BintrBot Broad Raw Uncertain Candidate Kline Backfill
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/backfill_uncertain_candidate_klines.py
User=root
Nice=19
IOSchedulingClass=idle
Environment=PYTHONUNBUFFERED=1
UNIT

cat > /etc/systemd/system/bintrbot-backfill-uncertain-candidates.timer <<'UNIT'
[Unit]
Description=Queue broad raw uncertain candidate backfill

[Timer]
OnBootSec=12min
OnUnitActiveSec=15min
AccuracySec=1min
Persistent=true
Unit=bintrbot-backfill-uncertain-candidates.service

[Install]
WantedBy=timers.target
UNIT

cat > "$ROOT/dataset-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== AI DATASET POLICY =========='
python3 - <<'PY'
import json
from pathlib import Path
for f in [
 "/root/bintrbot/state/dataset_collection_policy.json",
 "/root/bintrbot/data/catalog/dataset_catalog.json",
 "/root/bintrbot/state/backfill_uncertain_candidates.json"
]:
    p=Path(f)
    print("\n---",p.name,"---")
    if not p.exists():
        print("missing");continue
    x=json.loads(p.read_text())
    keys=[
      "status","physical_partition_count","symbol_count","rows_catalogued",
      "strict_ready_symbols","strict_boundary_pending_symbols",
      "targets_total","jobs_remaining","backfill_started"
    ]
    for k in keys:
        if k in x:
            v=x[k]
            print(k.upper(),"=",len(v) if isinstance(v,list) else v)
PY
echo
echo '========== PROFILES =========='
for f in /root/bintrbot/data/catalog/profiles/*.json; do
  [ -f "$f" ] || continue
  python3 - "$f" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
print(x.get("profile"),"status=",x.get("status"))
PY
done
echo
echo '========== TIMERS =========='
systemctl is-active bintrbot-dataset-catalog.timer || true
systemctl is-active bintrbot-backfill-uncertain-candidates.timer || true
SH
chmod +x "$ROOT/dataset-status.sh"

"$PY" -m py_compile   "$ROOT/app/phase0_gate.py"   "$ROOT/app/build_ai_dataset_catalog.py"   "$ROOT/app/backfill_uncertain_candidate_klines.py"

"$PY" "$ROOT/app/build_ai_dataset_catalog.py"

systemctl daemon-reload
systemctl enable --now bintrbot-dataset-catalog.timer
systemctl enable --now bintrbot-backfill-uncertain-candidates.timer
systemctl start bintrbot-backfill-uncertain-candidates.service

echo
echo '========== PHASE 0 =========='
"$ROOT/phase0-status.sh"

echo
echo '========== DATASETS =========='
"$ROOT/dataset-status.sh"

echo
echo '========== CORE SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true

echo
echo "AI_DATASET_FOUNDATION=PASS"
