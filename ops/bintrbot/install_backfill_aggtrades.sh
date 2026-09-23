#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

"$PIP" install -q pyarrow
mkdir -p "$ROOT/app" "$ROOT/data/bronze/agg_trades" "$ROOT/state"

cat > "$ROOT/app/backfill_aggtrades.py" <<'PY'
from __future__ import annotations

import asyncio, hashlib, json, os, shutil, time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
META = ROOT / "data/meta/symbols.json"
FIRST = ROOT / "state/first_klines.json"
STATE = ROOT / "state/backfill_aggtrades.json"
OUT = ROOT / "data/bronze/agg_trades"

MIN_FREE = 20 * 1024**3
REQ_GAP = 1.0
CHUNK_ROWS = 100000

URL = {
    1: "https://api.binance.me/api/v3/aggTrades",
    3: "https://cloudme-tr.2meta.app/api/v1/aggTrades",
}

SCHEMA = pa.schema([
    ("symbol", pa.string()),
    ("symbol_type", pa.int8()),
    ("agg_trade_id", pa.int64()),
    ("price", pa.string()),
    ("qty", pa.string()),
    ("first_trade_id", pa.int64()),
    ("last_trade_id", pa.int64()),
    ("trade_time_ms", pa.int64()),
    ("buyer_maker", pa.bool_()),
    ("best_match", pa.bool_()),
])

def now_ms():
    return time.time_ns() // 1_000_000

def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
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

def disk_ok():
    return shutil.disk_usage("/").free >= MIN_FREE

async def get(session, url, params):
    last = None
    for n in range(12):
        if not disk_ok():
            raise RuntimeError("DISK_GUARD_STOP")
        await asyncio.sleep(REQ_GAP)
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    x = await r.json(content_type=None)
                    return x.get("data", x) if isinstance(x, dict) else x
                body = await r.text()
                if r.status in (418, 429):
                    delay = r.headers.get("Retry-After")
                    await asyncio.sleep(float(delay) if delay else min(20 * (n + 1), 180))
                    continue
                if 500 <= r.status < 600:
                    await asyncio.sleep(min(2 ** n, 30))
                    continue
                raise RuntimeError(f"HTTP_{r.status}:{body[:250]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = repr(e)
            await asyncio.sleep(min(2 ** n, 30))
    raise RuntimeError(f"RETRY_EXHAUSTED:{last}")

def ym(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")

def write_chunk(symbol, stype, month, rows):
    if not rows:
        return None
    y, m = month.split("-")
    folder = OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}"
    folder.mkdir(parents=True, exist_ok=True)

    first_id = int(rows[0]["agg_trade_id"])
    last_id = int(rows[-1]["agg_trade_id"])
    final = folder / f"part-{first_id:020d}-{last_id:020d}.parquet"
    tmp = final.with_suffix(".parquet.tmp")

    pq.write_table(
        pa.Table.from_pylist(rows, schema=SCHEMA),
        tmp,
        compression="zstd",
        compression_level=6,
        write_statistics=True,
    )
    os.replace(tmp, final)

    info = {
        "status": "COMPLETE",
        "symbol": symbol,
        "symbol_type": stype,
        "year_month": month,
        "row_count": len(rows),
        "first_agg_trade_id": first_id,
        "last_agg_trade_id": last_id,
        "first_trade_time_ms": int(rows[0]["trade_time_ms"]),
        "last_trade_time_ms": int(rows[-1]["trade_time_ms"]),
        "sha256": sha256(final),
        "file_bytes": final.stat().st_size,
        "file": str(final.relative_to(ROOT)),
        "completed_at_ms": now_ms(),
    }
    atomic_json(final.with_suffix(".manifest.json"), info)
    return info

async def seed_first_id(session, symbol, api, stype, first_ms, cutoff):
    end = min(first_ms + 60 * 60 * 1000 - 1, cutoff)
    data = await get(session, URL[stype], {
        "symbol": api,
        "startTime": first_ms,
        "endTime": end,
        "limit": 1,
    })
    if isinstance(data, list) and data:
        return int(data[0]["a"])
    return None

async def process_symbol(session, row, first_ms, cutoff, state):
    symbol = str(row["symbol"])
    stype = int(row.get("type", 1))
    if stype not in URL:
        state["symbols"][symbol] = {"status": "UNSUPPORTED", "symbol_type": stype}
        atomic_json(STATE, state)
        return

    api = symbol.replace("_", "") if stype == 1 else symbol
    ss = state["symbols"].setdefault(symbol, {
        "status": "PENDING",
        "symbol_type": stype,
        "next_id": None,
        "last_id": None,
        "rows": 0,
        "parts": 0,
        "id_gaps": 0,
    })

    if ss.get("status") == "COMPLETE":
        return

    next_id = ss.get("next_id")
    if next_id is None:
        first_id = await seed_first_id(session, symbol, api, stype, int(first_ms), cutoff)
        if first_id is None:
            ss["status"] = "NO_TRADES_AT_FIRST_KLINE"
            ss["updated_at_ms"] = now_ms()
            atomic_json(STATE, state)
            print("NO_SEED", symbol, flush=True)
            return
        next_id = first_id
        ss["next_id"] = first_id
        ss["status"] = "RUNNING"
        atomic_json(STATE, state)
        print("SEED", symbol, f"agg_id={first_id}", flush=True)

    buf = []
    buf_month = None
    prev_id = ss.get("last_id")

    async def flush():
        nonlocal buf, buf_month, prev_id, next_id
        if not buf:
            return
        info = await asyncio.to_thread(write_chunk, symbol, stype, buf_month, buf)
        ss["rows"] = int(ss.get("rows", 0)) + int(info["row_count"])
        ss["parts"] = int(ss.get("parts", 0)) + 1
        ss["last_id"] = int(info["last_agg_trade_id"])
        ss["next_id"] = int(info["last_agg_trade_id"]) + 1
        ss["last_trade_time_ms"] = int(info["last_trade_time_ms"])
        ss["updated_at_ms"] = now_ms()
        state["rows_total"] = sum(int(x.get("rows", 0)) for x in state["symbols"].values())
        state["parts_total"] = sum(int(x.get("parts", 0)) for x in state["symbols"].values())
        atomic_json(STATE, state)
        print("CHUNK_OK", symbol, buf_month, f"rows={info['row_count']}", f"last_id={info['last_agg_trade_id']}", flush=True)
        prev_id = int(info["last_agg_trade_id"])
        next_id = prev_id + 1
        buf = []

    while True:
        data = await get(session, URL[stype], {
            "symbol": api,
            "fromId": int(next_id),
            "limit": 1000,
        })

        if not isinstance(data, list) or not data:
            await flush()
            ss["status"] = "COMPLETE"
            ss["completed_at_ms"] = now_ms()
            atomic_json(STATE, state)
            print("SYMBOL_COMPLETE", symbol, f"rows={ss['rows']}", flush=True)
            return

        usable = []
        reached_cutoff = False

        for x in data:
            aid = int(x["a"])
            t = int(x["T"])
            if t > cutoff:
                reached_cutoff = True
                break
            if aid < int(next_id):
                continue
            usable.append(x)

        if not usable:
            await flush()
            if reached_cutoff or int(data[0]["T"]) > cutoff:
                ss["status"] = "COMPLETE"
                ss["completed_at_ms"] = now_ms()
                atomic_json(STATE, state)
                print("SYMBOL_COMPLETE", symbol, f"rows={ss['rows']}", flush=True)
                return
            raise RuntimeError(f"NON_ADVANCING_PAGE next_id={next_id}")

        first_returned = int(usable[0]["a"])
        if first_returned > int(next_id):
            ss["id_gaps"] = int(ss.get("id_gaps", 0)) + 1
            ss["status"] = "ID_GAP"
            ss["expected_id"] = int(next_id)
            ss["returned_id"] = first_returned
            atomic_json(STATE, state)
            raise RuntimeError(f"ID_GAP expected={next_id} got={first_returned}")

        for x in usable:
            aid = int(x["a"])
            t = int(x["T"])
            if prev_id is not None and aid <= int(prev_id):
                continue
            month = ym(t)
            if buf_month is None:
                buf_month = month
            if month != buf_month:
                await flush()
                buf_month = month

            buf.append({
                "symbol": symbol,
                "symbol_type": stype,
                "agg_trade_id": aid,
                "price": str(x["p"]),
                "qty": str(x["q"]),
                "first_trade_id": int(x["f"]),
                "last_trade_id": int(x["l"]),
                "trade_time_ms": t,
                "buyer_maker": bool(x["m"]),
                "best_match": bool(x.get("M", True)),
            })
            prev_id = aid

            if len(buf) >= CHUNK_ROWS:
                await flush()
                buf_month = None

        next_id = int(usable[-1]["a"]) + 1

        if reached_cutoff or len(data) < 1000:
            await flush()
            ss["status"] = "COMPLETE"
            ss["completed_at_ms"] = now_ms()
            atomic_json(STATE, state)
            print("SYMBOL_COMPLETE", symbol, f"rows={ss['rows']}", flush=True)
            return

async def main():
    meta = load_json(META, {})
    first = load_json(FIRST, {})
    symbols = meta.get("symbols", [])
    cutoff = (now_ms() // 60000) * 60000 - 1

    state = load_json(STATE, {
        "version": 1,
        "status": "RUNNING",
        "created_at_ms": now_ms(),
        "cutoff_ms": cutoff,
        "symbols_total": len(symbols),
        "rows_total": 0,
        "parts_total": 0,
        "symbols": {},
        "errors": {},
    })

    state["status"] = "RUNNING"
    state["cutoff_ms"] = cutoff
    state["symbols_total"] = len(symbols)
    atomic_json(STATE, state)

    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-aggtrade-backfill/1.0"}) as session:
        for row in symbols:
            if not disk_ok():
                state["status"] = "DISK_GUARD_STOP"
                state["free_bytes"] = shutil.disk_usage("/").free
                atomic_json(STATE, state)
                print("DISK_GUARD_STOP", flush=True)
                return

            symbol = str(row["symbol"])
            first_ms = first.get(symbol)
            if first_ms is None:
                state["errors"][symbol] = "FIRST_KLINE_UNKNOWN"
                atomic_json(STATE, state)
                continue

            try:
                await process_symbol(session, row, int(first_ms), cutoff, state)
                state["errors"].pop(symbol, None)
            except Exception as e:
                state["errors"][symbol] = repr(e)
                atomic_json(STATE, state)
                print("SYMBOL_ERROR", symbol, repr(e), flush=True)

    if state["errors"]:
        state["status"] = "INCOMPLETE_ERRORS"
    else:
        state["status"] = "COMPLETE"
    state["finished_at_ms"] = now_ms()
    atomic_json(STATE, state)
    print("BACKFILL_STATUS", state["status"], flush=True)

asyncio.run(main())
PY

cat > /etc/systemd/system/bintrbot-backfill-aggtrades.service <<'UNIT'
[Unit]
Description=Binance TR Historical Aggregate Trades Backfill
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/backfill_aggtrades.py
Restart=no
User=root
Environment=PYTHONUNBUFFERED=1
Nice=15
IOSchedulingClass=best-effort
IOSchedulingPriority=7

[Install]
WantedBy=multi-user.target
UNIT

cat > /root/bintrbot/trades-status.sh <<'SH'
#!/usr/bin/env bash
echo '========== LIVE =========='
systemctl is-active bintrbot-collector.service || true
echo '========== KLINES =========='
systemctl is-active bintrbot-backfill-klines.service || true
echo '========== AGGTRADES =========='
systemctl is-active bintrbot-backfill-aggtrades.service || true
echo '========== STATE =========='
python3 - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/state/backfill_aggtrades.json")
if not p.exists():
    print("state not ready")
    raise SystemExit
s=json.loads(p.read_text())
print("STATUS=",s.get("status"))
print("SYMBOLS_TOTAL=",s.get("symbols_total"))
print("SYMBOLS_STARTED=",len(s.get("symbols",{})))
print("SYMBOLS_COMPLETE=",sum(1 for x in s.get("symbols",{}).values() if x.get("status")=="COMPLETE"))
print("ROWS_TOTAL=",s.get("rows_total",0))
print("PARTS_TOTAL=",s.get("parts_total",0))
print("ERRORS=",len(s.get("errors",{})))
for k,v in list(s.get("errors",{}).items())[:8]:
    print("ERROR",k,v)
PY
echo '========== DATA =========='
du -sh /root/bintrbot/data/bronze/agg_trades 2>/dev/null || true
find /root/bintrbot/data/bronze/agg_trades -name '*.parquet' 2>/dev/null | wc -l
echo '========== DISK =========='
df -hT /
echo '========== LOG =========='
journalctl -u bintrbot-backfill-aggtrades.service -n 35 --no-pager
SH

chmod +x /root/bintrbot/trades-status.sh
systemctl daemon-reload
systemctl enable --now bintrbot-backfill-aggtrades.service
sleep 15
/root/bintrbot/trades-status.sh
