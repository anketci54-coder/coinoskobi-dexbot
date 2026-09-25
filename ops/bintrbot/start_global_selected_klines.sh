#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

test -x "$PY" || { echo "MISSING_VENV=$PY"; exit 2; }
test -f "$ROOT/data/meta/symbols.json" || { echo "MISSING_TR_META"; exit 2; }

mkdir -p   "$ROOT/app"   "$ROOT/state"   "$ROOT/data/global/bronze/klines_1m"   "$ROOT/data/global/meta"   /etc/systemd/system/bintrbot-global-klines.service.d

"$PY" - <<'PY' || "$PIP" install -q aiohttp pyarrow
import aiohttp, pyarrow
print("GLOBAL_DEPS=OK")
PY

APP="$ROOT/app/backfill_global_selected_klines.py"
if [ -f "$APP" ]; then
  cp -a "$APP" "$ROOT/state/backfill_global_selected_klines.py.pre_$TS.bak"
fi

cat > "$APP" <<'PY'
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

ROOT = Path("/root/bintrbot")
TR_META = ROOT / "data/meta/symbols.json"
OUT = ROOT / "data/global/bronze/klines_1m"
META_OUT = ROOT / "data/global/meta/selected_spot_usdt.json"
STATE = ROOT / "state/backfill_global_selected_klines.json"

BASE = "https://data-api.binance.vision"
EXCHANGE_INFO = BASE + "/api/v3/exchangeInfo"
KLINES = BASE + "/api/v3/klines"

MIN_FREE = 48 * 1024**3
REQ_GAP = 0.35
LIMIT = 1000
MINUTE = 60_000

SCHEMA = pa.schema([
    ("source_venue", pa.string()),
    ("symbol", pa.string()),
    ("tr_symbol", pa.string()),
    ("base_asset", pa.string()),
    ("quote_asset", pa.string()),
    ("open_time_ms", pa.int64()),
    ("open", pa.string()),
    ("high", pa.string()),
    ("low", pa.string()),
    ("close", pa.string()),
    ("volume", pa.string()),
    ("close_time_ms", pa.int64()),
    ("quote_volume", pa.string()),
    ("trade_count", pa.int64()),
    ("taker_buy_base_volume", pa.string()),
    ("taker_buy_quote_volume", pa.string()),
    ("ignore", pa.string()),
])

def now_ms():
    return time.time_ns() // 1_000_000

def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def free_bytes():
    return shutil.disk_usage("/").free

def disk_ok():
    return free_bytes() >= MIN_FREE

async def get_json(session, url, params=None):
    last = None
    for n in range(12):
        if not disk_ok():
            raise RuntimeError("DISK_GUARD_STOP")
        await asyncio.sleep(REQ_GAP)
        try:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
                body = await r.text()
                if r.status in (418, 429):
                    retry = r.headers.get("Retry-After")
                    await asyncio.sleep(float(retry) if retry else min(10 * (n + 1), 180))
                    continue
                if 500 <= r.status < 600:
                    await asyncio.sleep(min(2 ** n, 30))
                    continue
                raise RuntimeError(f"HTTP_{r.status}:{body[:250]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = repr(e)
            await asyncio.sleep(min(2 ** n, 30))
    raise RuntimeError(f"RETRY_EXHAUSTED:{last}")

def month_start_ms(dt: datetime):
    return int(datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp() * 1000)

def next_month_ms(ms: int):
    d = datetime.fromtimestamp(ms / 1000, timezone.utc)
    if d.month == 12:
        n = datetime(d.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        n = datetime(d.year, d.month + 1, 1, tzinfo=timezone.utc)
    return int(n.timestamp() * 1000)

def ym(ms: int):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")

def manifest_path(symbol: str, month: str):
    y, m = month.split("-")
    return OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}" / "manifest.json"

def data_path(symbol: str, month: str):
    y, m = month.split("-")
    return OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}" / "klines.parquet"

def complete_partition(symbol: str, month: str):
    mp = manifest_path(symbol, month)
    dp = data_path(symbol, month)
    if not mp.exists() or not dp.exists():
        return False
    try:
        x = json.loads(mp.read_text())
        return x.get("status") == "COMPLETE" and x.get("sha256") == sha256(dp)
    except Exception:
        return False

def write_month(symbol, tr_symbol, base_asset, month, rows, requested_start, requested_end):
    if not disk_ok():
        raise RuntimeError("DISK_GUARD_STOP")
    dp = data_path(symbol, month)
    mp = manifest_path(symbol, month)
    dp.parent.mkdir(parents=True, exist_ok=True)

    out = []
    for x in rows:
        out.append({
            "source_venue": "BINANCE_GLOBAL_SPOT",
            "symbol": symbol,
            "tr_symbol": tr_symbol,
            "base_asset": base_asset,
            "quote_asset": "USDT",
            "open_time_ms": int(x[0]),
            "open": str(x[1]),
            "high": str(x[2]),
            "low": str(x[3]),
            "close": str(x[4]),
            "volume": str(x[5]),
            "close_time_ms": int(x[6]),
            "quote_volume": str(x[7]),
            "trade_count": int(x[8]),
            "taker_buy_base_volume": str(x[9]),
            "taker_buy_quote_volume": str(x[10]),
            "ignore": str(x[11]),
        })

    tmp = dp.with_suffix(".parquet.tmp")
    pq.write_table(
        pa.Table.from_pylist(out, schema=SCHEMA),
        tmp,
        compression="zstd",
        compression_level=6,
        write_statistics=True,
    )
    os.replace(tmp, dp)

    times = [r["open_time_ms"] for r in out]
    gaps = []
    for a, b in zip(times, times[1:]):
        if b - a > MINUTE:
            gaps.append({
                "after_open_time_ms": a,
                "next_open_time_ms": b,
                "missing_minutes": (b - a) // MINUTE - 1,
            })

    manifest = {
        "status": "COMPLETE",
        "source_venue": "BINANCE_GLOBAL_SPOT",
        "source_endpoint": KLINES,
        "symbol": symbol,
        "tr_symbol": tr_symbol,
        "base_asset": base_asset,
        "quote_asset": "USDT",
        "interval": "1m",
        "year_month": month,
        "requested_start_ms": requested_start,
        "requested_end_ms": requested_end,
        "row_count": len(out),
        "first_open_time_ms": times[0] if times else None,
        "last_open_time_ms": times[-1] if times else None,
        "gap_count": len(gaps),
        "largest_gap_minutes": max((g["missing_minutes"] for g in gaps), default=0),
        "sha256": sha256(dp),
        "file_bytes": dp.stat().st_size,
        "completed_at_ms": now_ms(),
    }
    atomic_json(mp, manifest)
    return manifest

async def discover_universe(session):
    tr = load_json(TR_META, {})
    tr_rows = tr.get("symbols", [])
    tr_by_base = {}
    for r in tr_rows:
        s = r.get("symbol")
        b = r.get("baseAsset")
        if isinstance(s, str) and s.endswith("_TRY") and isinstance(b, str):
            tr_by_base.setdefault(b, s)

    ex = await get_json(session, EXCHANGE_INFO)
    global_rows = ex.get("symbols", []) if isinstance(ex, dict) else []
    candidates = {}
    for r in global_rows:
        if (
            r.get("quoteAsset") == "USDT"
            and r.get("status") == "TRADING"
            and r.get("baseAsset") in tr_by_base
        ):
            candidates[r["symbol"]] = {
                "global_symbol": r["symbol"],
                "tr_symbol": tr_by_base[r["baseAsset"]],
                "base_asset": r["baseAsset"],
                "quote_asset": "USDT",
                "selection_reason": "CURRENT_BINANCE_TR_BASE_MATCH",
            }

    for benchmark in ("BTCUSDT", "ETHUSDT", "BNBUSDT"):
        r = next((x for x in global_rows if x.get("symbol") == benchmark and x.get("status") == "TRADING"), None)
        if r:
            base = r["baseAsset"]
            candidates[benchmark] = {
                "global_symbol": benchmark,
                "tr_symbol": tr_by_base.get(base),
                "base_asset": base,
                "quote_asset": "USDT",
                "selection_reason": "BENCHMARK" if base not in tr_by_base else "CURRENT_BINANCE_TR_BASE_MATCH+BENCHMARK",
            }

    matched_bases = {x["base_asset"] for x in candidates.values()}
    unmatched = sorted(
        [
            {"tr_symbol": s, "base_asset": b}
            for b, s in tr_by_base.items()
            if b not in matched_bases
        ],
        key=lambda x: x["tr_symbol"],
    )

    obj = {
        "schema_version": 1,
        "generated_at_ms": now_ms(),
        "source": EXCHANGE_INFO,
        "policy": "Current Binance TR base assets matched to active Binance Global Spot USDT pairs; BTC/ETH/BNB benchmarks forced when available.",
        "selected_count": len(candidates),
        "selected": [candidates[k] for k in sorted(candidates)],
        "unmatched_tr_count": len(unmatched),
        "unmatched_tr": unmatched,
    }
    atomic_json(META_OUT, obj)
    return obj

async def first_kline(session, symbol):
    x = await get_json(session, KLINES, {
        "symbol": symbol,
        "interval": "1m",
        "startTime": 0,
        "limit": 1,
    })
    if isinstance(x, list) and x:
        return int(x[0][0])
    return None

async def fetch_month(session, symbol, start_ms, end_ms):
    rows = []
    cursor = start_ms
    while cursor <= end_ms:
        x = await get_json(session, KLINES, {
            "symbol": symbol,
            "interval": "1m",
            "startTime": cursor,
            "endTime": end_ms,
            "limit": LIMIT,
        })
        if not isinstance(x, list) or not x:
            break
        rows.extend(x)
        nxt = int(x[-1][0]) + MINUTE
        if nxt <= cursor:
            raise RuntimeError("NON_ADVANCING_KLINE_PAGE")
        cursor = nxt
        if len(x) < LIMIT:
            break

    dedup = {}
    for r in rows:
        ot = int(r[0])
        if start_ms <= ot <= end_ms:
            dedup[ot] = r
    return [dedup[k] for k in sorted(dedup)]

async def main():
    headers = {"User-Agent": "bintrbot-global-selected-kline-backfill/1.0"}
    connector = aiohttp.TCPConnector(limit=4, ttl_dns_cache=300)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        universe = await discover_universe(session)
        selected = universe["selected"]
        cutoff = (now_ms() // MINUTE) * MINUTE - 1

        state = load_json(STATE, {
            "schema_version": 1,
            "status": "RUNNING",
            "created_at_ms": now_ms(),
            "source_venue": "BINANCE_GLOBAL_SPOT",
            "endpoint": BASE,
            "selection_policy": universe["policy"],
            "symbols": {},
            "errors": {},
            "rows_total": 0,
            "partitions_total": 0,
        })
        state["status"] = "RUNNING"
        state["cutoff_ms"] = cutoff
        state["symbols_total"] = len(selected)
        state["selected_universe_generated_at_ms"] = universe["generated_at_ms"]
        atomic_json(STATE, state)

        for row in selected:
            if not disk_ok():
                state["status"] = "DISK_GUARD_STOP"
                state["free_gib"] = round(free_bytes() / 1024**3, 2)
                atomic_json(STATE, state)
                print("GLOBAL_DISK_GUARD_STOP", flush=True)
                return

            symbol = row["global_symbol"]
            tr_symbol = row.get("tr_symbol")
            base_asset = row["base_asset"]
            ss = state["symbols"].setdefault(symbol, {
                "status": "PENDING",
                "tr_symbol": tr_symbol,
                "base_asset": base_asset,
                "rows": 0,
                "partitions": 0,
            })

            try:
                first = ss.get("first_open_time_ms")
                if first is None:
                    first = await first_kline(session, symbol)
                    if first is None:
                        ss["status"] = "NO_KLINES"
                        ss["updated_at_ms"] = now_ms()
                        atomic_json(STATE, state)
                        print("GLOBAL_NO_KLINES", symbol, flush=True)
                        continue
                    ss["first_open_time_ms"] = first
                    ss["status"] = "RUNNING"
                    atomic_json(STATE, state)
                    print("GLOBAL_SEED", symbol, datetime.fromtimestamp(first/1000, timezone.utc).isoformat(), flush=True)

                month_ms = month_start_ms(datetime.fromtimestamp(first / 1000, timezone.utc))
                while month_ms <= cutoff:
                    nm = next_month_ms(month_ms)
                    req_start = max(first, month_ms)
                    req_end = min(cutoff, nm - 1)
                    month = ym(month_ms)

                    if complete_partition(symbol, month):
                        month_ms = nm
                        continue

                    rows = await fetch_month(session, symbol, req_start, req_end)
                    if rows:
                        info = await asyncio.to_thread(
                            write_month,
                            symbol, tr_symbol, base_asset, month, rows, req_start, req_end
                        )
                        ss["rows"] = int(ss.get("rows", 0)) + int(info["row_count"])
                        ss["partitions"] = int(ss.get("partitions", 0)) + 1
                        ss["last_month"] = month
                        ss["last_open_time_ms"] = info["last_open_time_ms"]
                        ss["updated_at_ms"] = now_ms()
                        state["rows_total"] = sum(int(v.get("rows", 0)) for v in state["symbols"].values())
                        state["partitions_total"] = sum(int(v.get("partitions", 0)) for v in state["symbols"].values())
                        atomic_json(STATE, state)
                        print("GLOBAL_MONTH_OK", symbol, month, f"rows={info['row_count']}", f"gaps={info['gap_count']}", flush=True)
                    else:
                        print("GLOBAL_MONTH_EMPTY", symbol, month, flush=True)

                    month_ms = nm

                ss["status"] = "COMPLETE"
                ss["completed_at_ms"] = now_ms()
                state["errors"].pop(symbol, None)
                atomic_json(STATE, state)
                print("GLOBAL_SYMBOL_COMPLETE", symbol, f"rows={ss.get('rows',0)}", flush=True)

            except RuntimeError as e:
                if str(e) == "DISK_GUARD_STOP":
                    state["status"] = "DISK_GUARD_STOP"
                    state["free_gib"] = round(free_bytes() / 1024**3, 2)
                    atomic_json(STATE, state)
                    print("GLOBAL_DISK_GUARD_STOP", flush=True)
                    return
                state["errors"][symbol] = repr(e)
                ss["status"] = "ERROR"
                atomic_json(STATE, state)
                print("GLOBAL_SYMBOL_ERROR", symbol, repr(e), flush=True)
            except Exception as e:
                state["errors"][symbol] = repr(e)
                ss["status"] = "ERROR"
                atomic_json(STATE, state)
                print("GLOBAL_SYMBOL_ERROR", symbol, repr(e), flush=True)

        state["status"] = "COMPLETE" if not state["errors"] else "INCOMPLETE_ERRORS"
        state["finished_at_ms"] = now_ms()
        atomic_json(STATE, state)
        print("GLOBAL_BACKFILL_STATUS", state["status"], flush=True)

asyncio.run(main())
PY

cat > /etc/systemd/system/bintrbot-global-klines.service <<'UNIT'
[Unit]
Description=BintrBot selected Binance Global Spot USDT 1m historical kline backfill
After=network-online.target bintrbot-collector.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/backfill_global_selected_klines.py
Restart=no
User=root
Environment=PYTHONUNBUFFERED=1
Nice=19
IOSchedulingClass=idle
CPUQuota=25%

[Install]
WantedBy=multi-user.target
UNIT

cat > "$ROOT/app/global_klines_guardian.py" <<'PY'
from __future__ import annotations
import json, shutil, subprocess, time, os
from pathlib import Path

ROOT=Path("/root/bintrbot")
OUT=ROOT/"state/global_klines_guardian.json"
LIVE=ROOT/"data/quality/guardian.json"
AGG=ROOT/"state/aggtrades_guardian.json"
MIN_FREE=48*1024**3

def load(p):
    try:return json.loads(p.read_text())
    except Exception:return {}

def active(unit):
    return subprocess.run(["systemctl","is-active","--quiet",unit],check=False).returncode==0

def atomic(p,obj):
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
    os.replace(t,p)

reasons=[]
free=shutil.disk_usage("/").free
live=load(LIVE)
agg=load(AGG)

if free < MIN_FREE:
    reasons.append("DISK_BELOW_48_GIB")
if not active("bintrbot-collector.service"):
    reasons.append("TR_COLLECTOR_NOT_ACTIVE")
if live and (live.get("status")!="PASS" or live.get("data_fresh") is not True):
    reasons.append("TR_LIVE_GUARDIAN_NOT_HEALTHY")
if agg and agg.get("status") not in (None,"PASS"):
    reasons.append("TR_AGGTRADES_GUARDIAN_NOT_HEALTHY")

glob_active=active("bintrbot-global-klines.service")
action="NONE"
if reasons and glob_active:
    subprocess.run(["systemctl","stop","bintrbot-global-klines.service"],check=False)
    action="GLOBAL_KLINES_STOPPED_FAIL_SAFE"

atomic(OUT,{
    "schema_version":1,
    "checked_at_ms":time.time_ns()//1_000_000,
    "status":"PASS" if not reasons else "STOPPED_OR_BLOCKED",
    "reasons":reasons,
    "action":action,
    "free_gib":round(free/1024**3,2),
    "tr_collector_active":active("bintrbot-collector.service"),
    "global_klines_active_after_check":active("bintrbot-global-klines.service"),
})
print(json.dumps(json.loads(OUT.read_text()),ensure_ascii=False,indent=2))
PY

cat > /etc/systemd/system/bintrbot-global-klines-guardian.service <<'UNIT'
[Unit]
Description=BintrBot Global kline safety guardian

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/global_klines_guardian.py
User=root
Nice=19
IOSchedulingClass=idle
UNIT

cat > /etc/systemd/system/bintrbot-global-klines-guardian.timer <<'UNIT'
[Unit]
Description=Check BintrBot Global kline safety every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=true
Unit=bintrbot-global-klines-guardian.service

[Install]
WantedBy=timers.target
UNIT

cat > "$ROOT/global-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== GLOBAL KLINES =========='
systemctl is-active bintrbot-global-klines.service || true
python3 - <<'PY'
import json
from pathlib import Path

for f in [
 "/root/bintrbot/data/global/meta/selected_spot_usdt.json",
 "/root/bintrbot/state/backfill_global_selected_klines.json",
 "/root/bintrbot/state/global_klines_guardian.json",
]:
    p=Path(f)
    print("\n---",p.name,"---")
    if not p.exists():
        print("not ready")
        continue
    x=json.loads(p.read_text())
    for k in [
      "selected_count","unmatched_tr_count","status","symbols_total",
      "rows_total","partitions_total","errors","free_gib","reasons","action"
    ]:
        if k in x:
            v=x[k]
            if k=="errors" and isinstance(v,dict): v=len(v)
            print(k.upper(),"=",v)
    if p.name=="backfill_global_selected_klines.json":
        sy=x.get("symbols",{})
        print("SYMBOLS_STARTED =",len(sy))
        print("SYMBOLS_COMPLETE =",sum(1 for v in sy.values() if v.get("status")=="COMPLETE"))
        running=[k for k,v in sy.items() if v.get("status")=="RUNNING"]
        if running: print("CURRENT =",running[-1])
PY
echo
echo '========== GLOBAL DATA =========='
du -sh /root/bintrbot/data/global 2>/dev/null || true
find /root/bintrbot/data/global/bronze/klines_1m -name '*.parquet' 2>/dev/null | wc -l
echo
echo '========== TR SAFETY =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-aggtrades.service || true
echo
echo '========== DISK =========='
df -h /
echo
echo '========== RECENT GLOBAL LOG =========='
journalctl -u bintrbot-global-klines.service -n 25 --no-pager || true
SH
chmod +x "$ROOT/global-status.sh"

"$PY" -m py_compile "$APP" "$ROOT/app/global_klines_guardian.py"

systemctl daemon-reload
systemctl enable --now bintrbot-global-klines-guardian.timer

# Fail-safe preflight.
"$PY" "$ROOT/app/global_klines_guardian.py"
GUARD="$("$PY" - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/state/global_klines_guardian.json")
x=json.loads(p.read_text()) if p.exists() else {}
print(x.get("status","UNKNOWN"))
PY
)"
if [ "$GUARD" != "PASS" ]; then
  echo "GLOBAL_START_BLOCKED=$GUARD"
  "$ROOT/global-status.sh"
  exit 3
fi

systemctl enable bintrbot-global-klines.service >/dev/null 2>&1 || true
systemctl start bintrbot-global-klines.service
sleep 15
"$PY" "$ROOT/app/global_klines_guardian.py"

echo
"$ROOT/global-status.sh"
echo
echo "GLOBAL_SELECTED_KLINES_START=PASS"
