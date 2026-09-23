#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

systemctl stop bintrbot-backfill-klines.service 2>/dev/null || true

cat > "$ROOT/app/backfill_klines.py" <<'PY'
from __future__ import annotations

import asyncio, hashlib, json, os, shutil, time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
META = ROOT / "data/meta/symbols.json"
OUT = ROOT / "data/bronze/klines_1m"
STATE = ROOT / "state/backfill_klines.json"
FIRST = ROOT / "state/first_klines.json"

START_MS = 1599609600000
MIN_FREE = 15 * 1024**3
WORKERS = 4
REQ_GAP = 0.30

URL = {
    1: "https://api.binance.me/api/v1/klines",
    3: "https://cloudme-tr.2meta.app/api/v1/klines",
}

SCHEMA = pa.schema([
    ("symbol", pa.string()),
    ("symbol_type", pa.int8()),
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

rate_lock = asyncio.Lock()
state_lock = asyncio.Lock()
next_req = 0.0
halt = asyncio.Event()

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

def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def disk_ok():
    free = shutil.disk_usage("/").free
    if free < MIN_FREE:
        halt.set()
        return False
    return True

async def throttle():
    global next_req
    async with rate_lock:
        now = time.monotonic()
        if next_req > now:
            await asyncio.sleep(next_req - now)
        next_req = max(time.monotonic(), next_req) + REQ_GAP

async def get(session, url, params):
    last = None
    for n in range(12):
        if halt.is_set():
            raise RuntimeError("DISK_GUARD_STOP")
        await throttle()
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    x = await r.json(content_type=None)
                    return x.get("data", x) if isinstance(x, dict) else x
                body = await r.text()
                if r.status in (418, 429):
                    delay = r.headers.get("Retry-After")
                    await asyncio.sleep(float(delay) if delay else min(15 * (n + 1), 120))
                    continue
                if 500 <= r.status < 600:
                    await asyncio.sleep(min(2 ** n, 30))
                    continue
                raise RuntimeError(f"HTTP_{r.status}:{body[:200]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = repr(e)
            await asyncio.sleep(min(2 ** n, 30))
    raise RuntimeError(f"RETRY_EXHAUSTED:{last}")

def month_key(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")

def next_ym(ym):
    y, m = map(int, ym.split("-"))
    if m == 12:
        return f"{y+1:04d}-01"
    return f"{y:04d}-{m+1:02d}"

def months(a, b):
    cur = a
    while True:
        yield cur
        if cur == b:
            return
        cur = next_ym(cur)

def bounds(ym):
    y, m = map(int, ym.split("-"))
    a = datetime(y, m, 1, tzinfo=timezone.utc)
    if m == 12:
        b = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    else:
        b = datetime(y, m + 1, 1, tzinfo=timezone.utc)
    return int(a.timestamp() * 1000), int(b.timestamp() * 1000) - 1

def mpath(symbol, ym):
    y, m = ym.split("-")
    return OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}" / "manifest.json"

def done(symbol, ym):
    p = mpath(symbol, ym)
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text()).get("status") == "COMPLETE"
    except Exception:
        return False

async def first_kline(session, row, cutoff, cache):
    symbol = str(row["symbol"])
    stype = int(row.get("type", 1))
    if stype not in URL:
        return None
    cached = cache.get(symbol)
    if isinstance(cached, int):
        return cached
    api = symbol.replace("_", "") if stype == 1 else symbol
    data = await get(session, URL[stype], {
        "symbol": api,
        "interval": "1m",
        "startTime": START_MS,
        "endTime": cutoff,
        "limit": 1,
    })
    first = None
    if isinstance(data, list) and data and isinstance(data[0], list):
        first = int(data[0][0])
    cache[symbol] = first
    atomic_json(FIRST, cache)
    print("FIRST_KLINE", symbol, first, flush=True)
    return first

def write_month(symbol, stype, ym, rows, source, req_start, req_end):
    y, m = ym.split("-")
    folder = OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}"
    folder.mkdir(parents=True, exist_ok=True)
    datafile = folder / "klines.parquet"
    manifest = folder / "manifest.json"

    rows.sort(key=lambda r: int(r[0]))
    dedup, seen = [], set()
    duplicates = gaps = largest = 0
    prev = None

    for r in rows:
        ot = int(r[0])
        if ot in seen:
            duplicates += 1
            continue
        seen.add(ot)
        if prev is not None and ot - prev > 60000:
            gaps += 1
            largest = max(largest, (ot - prev) // 60000 - 1)
        prev = ot
        dedup.append({
            "symbol": symbol,
            "symbol_type": stype,
            "open_time_ms": ot,
            "open": str(r[1]),
            "high": str(r[2]),
            "low": str(r[3]),
            "close": str(r[4]),
            "volume": str(r[5]),
            "close_time_ms": int(r[6]),
            "quote_volume": str(r[7]),
            "trade_count": int(r[8]),
            "taker_buy_base_volume": str(r[9]),
            "taker_buy_quote_volume": str(r[10]),
            "ignore": str(r[11]) if len(r) > 11 else "",
        })

    checksum = None
    size = 0
    if dedup:
        tmp = folder / "klines.parquet.tmp"
        pq.write_table(
            pa.Table.from_pylist(dedup, schema=SCHEMA),
            tmp,
            compression="zstd",
            compression_level=6,
            write_statistics=True,
        )
        os.replace(tmp, datafile)
        checksum = digest(datafile)
        size = datafile.stat().st_size
    else:
        datafile.unlink(missing_ok=True)

    info = {
        "status": "COMPLETE",
        "symbol": symbol,
        "symbol_type": stype,
        "interval": "1m",
        "year_month": ym,
        "row_count": len(dedup),
        "duplicate_count_removed": duplicates,
        "gap_count": gaps,
        "largest_gap_minutes": largest,
        "first_open_time_ms": dedup[0]["open_time_ms"] if dedup else None,
        "last_open_time_ms": dedup[-1]["open_time_ms"] if dedup else None,
        "requested_start_ms": req_start,
        "requested_end_ms": req_end,
        "sha256": checksum,
        "file_bytes": size,
        "source": source,
        "completed_at_ms": now_ms(),
    }
    atomic_json(manifest, info)
    return info

async def download(session, symbol, api, stype, ym, cutoff):
    a, b = bounds(ym)
    a = max(a, START_MS)
    b = min(b, cutoff)
    cursor, rows = a, []
    while cursor <= b:
        if not disk_ok():
            raise RuntimeError("DISK_GUARD_STOP")
        data = await get(session, URL[stype], {
            "symbol": api,
            "interval": "1m",
            "startTime": cursor,
            "endTime": b,
            "limit": 1000,
        })
        if not isinstance(data, list) or not data:
            break
        valid = [r for r in data if isinstance(r, list) and len(r) >= 11 and a <= int(r[0]) <= b]
        if not valid:
            break
        rows.extend(valid)
        nxt = int(valid[-1][0]) + 60000
        if nxt <= cursor:
            raise RuntimeError("NON_ADVANCING_CURSOR")
        cursor = nxt
        if len(data) < 1000:
            break
    return await asyncio.to_thread(write_month, symbol, stype, ym, rows, URL[stype], a, b)

async def main():
    meta = json.loads(META.read_text())
    symbols = meta.get("symbols", [])
    cutoff = (now_ms() // 60000) * 60000 - 1
    last_month = month_key(cutoff)
    cache = load_json(FIRST, {})

    progress = {
        "status": "DISCOVERING_FIRST_KLINES",
        "started_at_ms": now_ms(),
        "cutoff_ms": cutoff,
        "symbols_total": len(symbols),
        "symbols_discovered": 0,
        "jobs_remaining_at_start": 0,
        "months_complete_this_run": 0,
        "rows_written_this_run": 0,
        "errors": {},
    }
    atomic_json(STATE, progress)

    q = asyncio.Queue()

    async with aiohttp.ClientSession(headers={"User-Agent":"bintrbot-historical/2.0"}) as session:
        for row in symbols:
            if halt.is_set():
                break
            symbol = str(row["symbol"])
            stype = int(row.get("type", 1))
            if stype not in URL:
                progress["errors"][symbol] = f"UNSUPPORTED_TYPE_{stype}"
                continue
            try:
                first = await first_kline(session, row, cutoff, cache)
            except Exception as e:
                progress["errors"][symbol] = repr(e)
                atomic_json(STATE, progress)
                continue
            progress["symbols_discovered"] += 1
            if first is None:
                continue
            api = symbol.replace("_", "") if stype == 1 else symbol
            for ym in months(month_key(max(first, START_MS)), last_month):
                if not done(symbol, ym):
                    await q.put((symbol, api, stype, ym))
            progress["jobs_remaining_at_start"] = q.qsize()
            atomic_json(STATE, progress)

        progress["status"] = "RUNNING"
        progress["jobs_remaining_at_start"] = q.qsize()
        atomic_json(STATE, progress)

        async def worker():
            while not halt.is_set():
                try:
                    symbol, api, stype, ym = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    info = await download(session, symbol, api, stype, ym, cutoff)
                    async with state_lock:
                        progress["months_complete_this_run"] += 1
                        progress["rows_written_this_run"] += int(info["row_count"])
                        progress["last_symbol"] = symbol
                        progress["last_month"] = ym
                        progress["jobs_remaining"] = q.qsize()
                        progress["updated_at_ms"] = now_ms()
                        atomic_json(STATE, progress)
                    print("MONTH_OK", symbol, ym, f"rows={info['row_count']}", f"gaps={info['gap_count']}", flush=True)
                except Exception as e:
                    if str(e) == "DISK_GUARD_STOP":
                        halt.set()
                    else:
                        async with state_lock:
                            progress["errors"][f"{symbol}:{ym}"] = repr(e)
                            atomic_json(STATE, progress)
                        print("MONTH_ERROR", symbol, ym, repr(e), flush=True)
                finally:
                    q.task_done()

        await asyncio.gather(*(worker() for _ in range(WORKERS)))

    if halt.is_set():
        progress["status"] = "DISK_GUARD_STOP"
        progress["free_bytes"] = shutil.disk_usage("/").free
    elif progress["errors"]:
        progress["status"] = "INCOMPLETE_ERRORS"
    else:
        progress["status"] = "COMPLETE"
    progress["finished_at_ms"] = now_ms()
    atomic_json(STATE, progress)
    print("BACKFILL_STATUS", progress["status"], flush=True)

asyncio.run(main())
PY

systemctl daemon-reload
systemctl restart bintrbot-backfill-klines.service
sleep 12
/root/bintrbot/history-status.sh
